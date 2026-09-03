"""Hive-Machine — local Perplexity Computer clone.

Sandboxed computer for the local LLM: files, code exec, web, terminal.
Workspace: ~/.hive/machine/workspace (jailed, no escape).
All LLM calls via Ollama / LM Studio only.
"""

from pathlib import Path
from hive.config import CONFIG_DIR

MACHINE_DIR = CONFIG_DIR / "machine"
WORKSPACE = MACHINE_DIR / "workspace"
HISTORY_DB = MACHINE_DIR / "machine.db"

__all__ = ["MACHINE_DIR", "WORKSPACE", "HISTORY_DB"]
