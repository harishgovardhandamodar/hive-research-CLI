"""User-defined workflows — end-to-end fulfillment, local-first.

3-tier per workflow (every workflow has):
  local-only      — no copies, no commits, no websearch, no web LLM, sensitive datasets, private reports, full logs (never committed, .gitignore *)
  core-workflow   — web allowed, commits allowed, logs except private datapoints (redacted)
  public          — all can be committed, public

Folder structure for every workflow <name>:
  ~/.hive/machine/workflows/<name>.yaml          # definition
  ~/.hive/machine/workflows/<name>/             # 3-tier definition outputs
    local-only/datasets, reports, logs (+ .gitignore *)
    core-workflow/reports, artifacts, logs, README
    public/reports, artifacts, logs, README
  ~/.hive/machine/workspace/<name>/             # 3-tier execution workspace (jailed)
    local-only/datasets, reports, artifacts, logs
    core-workflow/...
    public/...

Execution is fully audited (audit.log_event) with severity/impact, access tier, and hash chain.
Supports Nvidia-PAIR routing per llm step.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Dict, List

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

from hive.config import load_config, AppConfig
from hive.llm import ChatMessage, chat, get_provider
from hive.machine import WORKFLOWS_DIR, MACHINE_DIR, workflow_dirs, workflow_base
from hive.machine.access import check_access, ensure_workflow_dirs, TIERS
from hive.machine.tools import dispatch_tool
from hive.machine.audit import log_event
from hive.machine.nvidia_pair import discover_all, pick_best, get_provider_for
from hive.machine.sensitive import redact

VAR_RE = re.compile(r"\$\{([^}]+)\}")

def _load_workflow(path: Path) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    if path.suffix in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError("pyyaml not installed: pip install pyyaml")
        return yaml.safe_load(text)
    return json.loads(text)

def _resolve_vars(template: str, context: Dict[str, str]) -> str:
    def repl(m):
        key = m.group(1).strip()
        if key.startswith("steps."):
            key = key[6:]
        if ".outputs" in key:
            key = key.split(".")[0]
        return context.get(key, m.group(0))
    return VAR_RE.sub(repl, template)

def _resolve_args(args: dict, context: Dict[str, str]) -> dict:
    out = {}
    for k, v in args.items():
        if isinstance(v, str):
            out[k] = _resolve_vars(v, context)
        else:
            out[k] = v
    return out

def _tier_path(workflow: str, access: str, path: str) -> str:
    """Resolve path relative to workflow's tier folder. Returns string relative to WORKSPACE/<workflow>/<tier>.jail will handle."""
    # If path already contains tier prefix, keep as is
    if any(path.startswith(f"{t}/") for t in TIERS):
        return path
    # Default: map write_file/read_file to reports, others to tier root
    # For simplicity, put all files under <tier>/reports or <tier>/artifacts/logs as needed
    # Heuristic: .md -> reports, .log/.json -> logs, else artifacts
    tier = access or "core-workflow"
    if path.endswith(".md"):
        return f"{workflow}/{tier}/reports/{path.lstrip('/')}"
    if path.endswith((".log", ".json", ".jsonl")):
        return f"{workflow}/{tier}/logs/{path.lstrip('/')}"
    # datasets only for local-only
    if tier == "local-only" and ("dataset" in path.lower() or path.startswith("datasets/")):
        return f"{workflow}/{tier}/datasets/{Path(path).name}"
    return f"{workflow}/{tier}/artifacts/{path.lstrip('/')}"

def list_workflows() -> List[Path]:
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(WORKFLOWS_DIR.glob("*.yaml")) + sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.json"))

def save_workflow(name: str, data: dict):
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    path = WORKFLOWS_DIR / f"{name}.yaml"
    # ensure 3-tier structure for definition and workspace
    ensure_workflow_dirs(WORKFLOWS_DIR / name)
    ensure_workflow_dirs(workflow_base(name))
    if yaml:
        path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    else:
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path

def run_workflow(
    workflow: str | Path,
    cfg: AppConfig | None = None,
    extra_vars: Dict[str, str] | None = None,
    dry_run: bool = False,
) -> dict:
    """Run workflow file or dict. Returns {id: output} context + audit."""
    cfg = cfg or load_config()
    # resolve workflow source
    wf = None
    wf_id = "workflow"
    if isinstance(workflow, dict):
        wf = workflow
        wf_id = wf.get("name", "workflow")
    elif isinstance(workflow, (str, Path)):
        p = Path(workflow)
        if p.exists() and p.is_file():
            wf = _load_workflow(p)
            wf_id = p.stem
        else:
            name = str(workflow)
            for ext in (".yaml", ".yml", ".json"):
                cand = WORKFLOWS_DIR / f"{name}{ext}"
                if cand.exists():
                    wf = _load_workflow(cand)
                    wf_id = name
                    break
            if wf is None:
                cand2 = WORKFLOWS_DIR / name
                if cand2.exists() and cand2.is_file():
                    wf = _load_workflow(cand2)
                    wf_id = cand2.stem
            if wf is None:
                raise FileNotFoundError(f"workflow not found: {workflow} (looked in {WORKFLOWS_DIR})")
    if wf is None:
        raise FileNotFoundError(str(workflow))

    # ensure 3-tier folders for this workflow (definition + workspace)
    ensure_workflow_dirs(WORKFLOWS_DIR / wf_id)
    dirs = ensure_workflow_dirs(workflow_base(wf_id))
    # workflow default access (top-level)
    wf_access = wf.get("access", "core-workflow")
    if wf_access not in TIERS:
        wf_access = "core-workflow"

    steps = wf.get("steps", [])
    context: Dict[str, str] = dict(extra_vars or {})
    outputs: Dict[str, str] = {}
    audit_events = []
    start = time.time()

    for step in steps:
        sid = step.get("id", f"step{len(outputs)+1}")
        tool = step.get("tool")
        llm_cfg = step.get("llm")
        args = step.get("args", {})
        step_access = step.get("access", wf_access)
        if step_access not in TIERS:
            step_access = wf_access

        # resolve path for file tools to tiered location
        if tool in ("write_file", "read_file", "list_files", "delete_path") and "path" in args:
            # only rewrite if path is not already tiered and not absolute
            orig_path = args["path"]
            if not any(orig_path.startswith(f"{t}/") for t in TIERS) and not str(orig_path).startswith("/"):
                # map to tiered workspace path
                args = dict(args)
                args["path"] = _tier_path(wf_id, step_access, str(orig_path))

        args = _resolve_args(args, {**context, **outputs})

        # enforce access control before any tool/llm
        if tool:
            check_access(tool, step_access, args)
        if llm_cfg is not None:
            # check llm web allowance
            check_access("llm_chat", step_access, {"prompt": llm_cfg.get("prompt", "") + str(args)})

        if llm_cfg is not None:
            prompt = llm_cfg.get("prompt") or args.get("prompt") or step.get("prompt") or ""
            prompt = _resolve_vars(prompt, {**context, **outputs})
            provider_name = llm_cfg.get("provider", "auto")
            model_name = llm_cfg.get("model", "")
            if provider_name == "auto":
                best = pick_best(cfg, prefer="fastest")
                if best:
                    provider_name = best.provider
                    model_name = best.model
                else:
                    provider_name = cfg.llm.provider
            orig_provider = cfg.llm.provider
            orig_ollama = cfg.llm.ollama_model
            orig_lmstudio = cfg.llm.lmstudio_model
            try:
                if provider_name == "nvidia":
                    from hive.llm.nvidia import NvidiaProvider
                    prov = NvidiaProvider(model=model_name or "meta/llama3-8b-instruct")
                    resp = prov.chat([ChatMessage(role="user", content=prompt)], temperature=cfg.llm.temperature)
                    out = resp.content
                    outputs[sid] = out
                    context[sid] = out
                    ev = log_event(tool="llm_chat", args={"provider": provider_name, "model": model_name, "prompt": prompt[:500], "access": step_access}, result=out, bytes_out=len(prompt), bytes_in=len(out), workflow_id=wf_id, model=model_name)
                    audit_events.append(ev)
                    continue
                if provider_name in ("ollama", "auto"):
                    cfg.llm.provider = "ollama"
                    if model_name:
                        cfg.llm.ollama_model = model_name
                elif provider_name == "lmstudio":
                    cfg.llm.provider = "lmstudio"
                    if model_name:
                        cfg.llm.lmstudio_model = model_name
                resp = chat(cfg, [ChatMessage(role="user", content=prompt)])
                out = resp.content
                outputs[sid] = out
                context[sid] = out
                log_event(tool="llm_chat", args={"provider": provider_name, "model": model_name, "prompt": prompt[:500], "access": step_access}, result=out, bytes_out=len(prompt), bytes_in=len(out), workflow_id=wf_id, model=model_name)
            finally:
                cfg.llm.provider = orig_provider
                cfg.llm.ollama_model = orig_ollama
                cfg.llm.lmstudio_model = orig_lmstudio

        if tool:
            if dry_run:
                outputs[sid] = f"[dry-run:{step_access}] would call {tool} {args}"
                continue
            result = dispatch_tool(tool, **args)
            # redact for core-workflow/public logs if sensitive
            if step_access != "local-only":
                # log redacted version for non-local tiers
                from hive.machine.sensitive import redact
                log_preview = redact(result[:2000])
            else:
                log_preview = result[:2000]
            log_event(tool=tool, args={**args, "access": step_access}, result=log_preview, bytes_out=len(str(args)), bytes_in=len(result), workflow_id=wf_id)
            outputs[sid] = result
            context[sid] = result

    elapsed = time.time() - start
    return {"workflow": wf_id, "outputs": outputs, "context": context, "elapsed": elapsed, "audit": audit_events, "dirs": {k: str(v) for k, v in dirs.items()}, "access": wf_access}

EXAMPLE_AI_AGENTS = {
    "name": "ai_agents_report",
    "description": "AI Agents research — local-first, audited (core-workflow: web allowed)",
    "access": "core-workflow",
    "steps": [
        {"id": "search", "tool": "web_search", "args": {"query": "AI Agents", "top_k": 5}, "access": "core-workflow"},
        {"id": "summarize", "llm": {"provider": "auto", "prompt": "Summarize these papers on AI Agents into 5 bullet findings, methods, and references:\n${search}\nBe concise, cite DOI/URL."}, "access": "core-workflow"},
        {"id": "write", "tool": "write_file", "args": {"path": "ai_agents_report.md", "content": "# AI Agents — Research Report\n\n${summarize}\n\n---\n*Generated local-first via ${search} — audited*"}, "access": "core-workflow"},
        {"id": "verify", "tool": "read_file", "args": {"path": "ai_agents_report.md"}, "access": "core-workflow"},
    ],
}

EXAMPLE_LOCAL_ONLY = {
    "name": "local_only_example",
    "description": "Local-only: sensitive datasets, no web, no commits",
    "access": "local-only",
    "steps": [
        {"id": "ingest", "tool": "write_file", "args": {"path": "datasets/private.csv", "content": "id,secret\n1,my_secret_data"}, "access": "local-only"},
        {"id": "analyze", "tool": "run_python", "args": {"code": "import pathlib; p=pathlib.Path('~/.hive/machine/workspace/local_only_example/local-only/datasets/private.csv').expanduser(); print(p.read_text()[:100])"}, "access": "local-only"},
        {"id": "report", "tool": "write_file", "args": {"path": "reports/private_report.md", "content": "# Private Report\n\n${analyze}"}, "access": "local-only"},
    ],
}
