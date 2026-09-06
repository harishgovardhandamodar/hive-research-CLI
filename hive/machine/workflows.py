"""User-defined workflows — end-to-end fulfillment, local-first.

Workflow file (~/.hive/machine/workflows/<name>.yaml or .json):
  name: ai_agents_report
  description: AI Agents research
  steps:
    - id: search
      tool: web_search
      args: {query: "AI Agents", top_k: 5}
    - id: write
      tool: write_file
      args: {path: "ai_agents_report.md", content: "${search}"}

Execution is fully audited (audit.log_event) with severity/impact,
supports Nvidia-PAIR routing per llm step (provider: ollama|lmstudio|nvidia|auto),
and sensitive-data redaction.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Dict, List

import httpx

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

from hive.config import load_config, AppConfig
from hive.llm import ChatMessage, chat, get_provider
from hive.machine import WORKFLOWS_DIR, MACHINE_DIR
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

def list_workflows() -> List[Path]:
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    return sorted(WORKFLOWS_DIR.glob("*.yaml")) + sorted(WORKFLOWS_DIR.glob("*.yml")) + sorted(WORKFLOWS_DIR.glob("*.json"))

def save_workflow(name: str, data: dict):
    WORKFLOWS_DIR.mkdir(parents=True, exist_ok=True)
    path = WORKFLOWS_DIR / f"{name}.yaml"
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
            # try as name in WORKFLOWS_DIR
            name = str(workflow)
            for ext in (".yaml", ".yml", ".json"):
                cand = WORKFLOWS_DIR / f"{name}{ext}"
                if cand.exists():
                    wf = _load_workflow(cand)
                    wf_id = name
                    break
            if wf is None:
                # also try WORKFLOWS_DIR / workflow as given
                cand2 = WORKFLOWS_DIR / name
                if cand2.exists() and cand2.is_file():
                    wf = _load_workflow(cand2)
                    wf_id = cand2.stem
            if wf is None:
                raise FileNotFoundError(f"workflow not found: {workflow} (looked in {WORKFLOWS_DIR})")
    if wf is None:
        raise FileNotFoundError(str(workflow))

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

        args = _resolve_args(args, {**context, **outputs})

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
                    ev = log_event(tool="llm_chat", args={"provider": provider_name, "model": model_name, "prompt": prompt[:500]}, result=out, bytes_out=len(prompt), bytes_in=len(out), workflow_id=wf_id, model=model_name)
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
                log_event(tool="llm_chat", args={"provider": provider_name, "model": model_name, "prompt": prompt[:500]}, result=out, bytes_out=len(prompt), bytes_in=len(out), workflow_id=wf_id, model=model_name)
            finally:
                cfg.llm.provider = orig_provider
                cfg.llm.ollama_model = orig_ollama
                cfg.llm.lmstudio_model = orig_lmstudio

        if tool:
            if dry_run:
                outputs[sid] = f"[dry-run] would call {tool} {args}"
                continue
            result = dispatch_tool(tool, **args)
            log_event(tool=tool, args=args, result=result, bytes_out=len(str(args)), bytes_in=len(result), workflow_id=wf_id)
            outputs[sid] = result
            context[sid] = result

    elapsed = time.time() - start
    return {"workflow": wf_id, "outputs": outputs, "context": context, "elapsed": elapsed, "audit": audit_events}

EXAMPLE_AI_AGENTS = {
    "name": "ai_agents_report",
    "description": "AI Agents research — local-first, audited",
    "steps": [
        {"id": "search", "tool": "web_search", "args": {"query": "AI Agents", "top_k": 5}},
        {"id": "summarize", "llm": {"provider": "auto", "prompt": "Summarize these papers on AI Agents into 5 bullet findings, methods, and references:\n${search}\nBe concise, cite DOI/URL."}},
        {"id": "write", "tool": "write_file", "args": {"path": "ai_agents_report.md", "content": "# AI Agents — Research Report\n\n${summarize}\n\n---\n*Generated local-first via ${search} — audited*"}},
        {"id": "verify", "tool": "read_file", "args": {"path": "ai_agents_report.md"}},
    ],
}
