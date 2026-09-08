"""Workbench profiles — narrow AGI specialization.

Each workbench is a YAML in ~/.hive/workbench/<name>.yaml and/or
personal-experiments/<name>/workbench.yaml.

Fields:
  name, description, domain, datasets, allowed_tools, model_preference,
  prompts, evaluation, constraints

This enables "build narrow spaced ideal AGI enabled workbench": one profile
per domain (e.g., fox-fraud, eda-credit, crypto, privacy, quai-lora) with
scoped memory, tools, and reward function.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Optional

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None  # type: ignore

from hive.config import CONFIG_DIR, EXPERIMENTS_DIR

WORKBENCH_DIR = CONFIG_DIR / "workbench"


# Built-in narrow profiles (seed from personal-experiments fox/*)
BUILTIN = {
    "fox-fraud": {
        "description": "Fox fraud-demo — transaction fraud detection (narrow AGI)",
        "domain": "fraud",
        "datasets": ["personal-experiments/fox/fraud-demo", "personal-experiments/fox/kaggle-demo"],
        "allowed_tools": ["list_files", "read_file", "run_python", "run_bash"],
        "model_preference": "ollama",
        "evaluation": "f1, precision@k",
        "constraints": "local-only, no web exfil",
    },
    "eda-credit": {
        "description": "EDA credit-card demo — exploratory analysis",
        "domain": "eda",
        "datasets": ["personal-experiments/fox/EDA-creditcard-demo"],
        "allowed_tools": ["list_files", "read_file", "write_file", "run_python"],
        "model_preference": "ollama",
        "evaluation": "artifacts, coverage",
    },
    "privacy": {
        "description": "Privacy analysis 2024 — gizmo privacy",
        "domain": "privacy",
        "datasets": ["personal-experiments/fox/privacy-analysis-2024"],
        "allowed_tools": ["read_file", "run_python", "llm_chat"],
        "model_preference": "auto",
        "evaluation": "audit pass, severity",
    },
    "quai-lora": {
        "description": "Quai LoRA — finetune experiment",
        "domain": "lora",
        "datasets": ["personal-experiments/quai-lora"],
        "allowed_tools": ["run_python", "run_bash", "read_file"],
        "model_preference": "nvidia",
        "evaluation": "loss, rank",
    },
    "diabetes": {
        "description": "Diabetes management — CareLink timeseries",
        "domain": "health",
        "datasets": ["~/.hive/machine/workspace/diabetes_management"],
        "allowed_tools": ["list_files", "read_file", "run_python", "write_file"],
        "model_preference": "ollama",
        "evaluation": "TIR, CV, report",
    },
}


def _ensure_dirs() -> None:
    WORKBENCH_DIR.mkdir(parents=True, exist_ok=True)
    # seed builtin if missing
    for name, data in BUILTIN.items():
        p = WORKBENCH_DIR / f"{name}.yaml"
        if not p.exists():
            _write_yaml(p, {"name": name, **data})


def _write_yaml(p: Path, data: dict) -> None:
    if yaml:
        p.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    else:
        p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _load_yaml(p: Path) -> dict:
    txt = p.read_text(encoding="utf-8")
    if p.suffix in (".yaml", ".yml"):
        if yaml is None:
            raise RuntimeError("pyyaml not installed")
        return yaml.safe_load(txt) or {}
    return json.loads(txt)


def list_workbenches() -> list[dict]:
    """List all workbenches: builtin + ~/.hive/workbench/*.yaml + personal-experiments/*/workbench.yaml."""
    _ensure_dirs()
    out: list[dict] = []
    seen: set[str] = set()
    # 1) config dir
    for p in sorted(WORKBENCH_DIR.glob("*.yaml")) + sorted(WORKBENCH_DIR.glob("*.yml")) + sorted(WORKBENCH_DIR.glob("*.json")):
        try:
            d = _load_yaml(p)
            name = d.get("name", p.stem)
            if name not in seen:
                out.append({"name": name, "path": str(p), "source": "config", **d})
                seen.add(name)
        except Exception:
            continue
    # 2) personal-experiments discovery
    if EXPERIMENTS_DIR and EXPERIMENTS_DIR.exists():
        for wb in EXPERIMENTS_DIR.rglob("workbench.yaml"):
            try:
                d = _load_yaml(wb)
                name = d.get("name", wb.parent.name)
                if name not in seen:
                    out.append({"name": name, "path": str(wb), "source": "legacy", **d})
                    seen.add(name)
            except Exception:
                continue
        # also auto-profile per top-level folder (fox/* etc) if no yaml
        for child in sorted(EXPERIMENTS_DIR.iterdir()):
            if child.is_dir() and child.name not in seen and not child.name.startswith("."):
                # heuristic: treat each top folder as workbench
                out.append(
                    {
                        "name": child.name,
                        "path": str(child),
                        "source": "auto",
                        "description": f"Auto workbench from {child.name}",
                        "domain": child.name,
                        "datasets": [str(child)],
                    }
                )
                seen.add(child.name)
        # nested fox/*
        fox = EXPERIMENTS_DIR / "fox"
        if fox.exists():
            for child in sorted(fox.iterdir()):
                if child.is_dir() and child.name not in seen:
                    out.append(
                        {
                            "name": child.name,
                            "path": str(child),
                            "source": "auto",
                            "description": f"Auto workbench fox/{child.name}",
                            "domain": child.name,
                            "datasets": [str(child)],
                        }
                    )
                    seen.add(child.name)
    return sorted(out, key=lambda x: x["name"])


def get_workbench(name: str) -> dict | None:
    for wb in list_workbenches():
        if wb["name"] == name:
            return wb
    return None


def resolve_workbench(name: str | None) -> str:
    """Resolve workbench name: explicit or auto from cwd or default."""
    if name:
        return name
    # auto: if cwd inside personal-experiments/<workbench>, use that
    cwd = Path.cwd().resolve()
    if EXPERIMENTS_DIR and EXPERIMENTS_DIR.exists():
        try:
            rel = cwd.relative_to(EXPERIMENTS_DIR.resolve())
            # first part is workbench
            if rel.parts:
                cand = rel.parts[0]
                # for fox/*, second part
                if cand == "fox" and len(rel.parts) > 1:
                    cand = rel.parts[1]
                if get_workbench(cand):
                    return cand
        except Exception:
            pass
    return "default"


def create_workbench(name: str, data: dict) -> Path:
    _ensure_dirs()
    p = WORKBENCH_DIR / f"{name}.yaml"
    full = {"name": name, "created_at": time.time(), **data}
    _write_yaml(p, full)
    return p


def delete_workbench(name: str) -> bool:
    p = WORKBENCH_DIR / f"{name}.yaml"
    if p.exists():
        p.unlink()
        return True
    # try yml
    for ext in (".yml", ".json"):
        q = WORKBENCH_DIR / f"{name}{ext}"
        if q.exists():
            q.unlink()
            return True
    return False
