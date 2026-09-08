"""Narrow-spaced workbench profiles — domain-specialized AGI scaffolding."""
from .profiles import (
    WORKBENCH_DIR,
    list_workbenches,
    get_workbench,
    create_workbench,
    delete_workbench,
    resolve_workbench,
)

__all__ = [
    "WORKBENCH_DIR",
    "list_workbenches",
    "get_workbench",
    "create_workbench",
    "delete_workbench",
    "resolve_workbench",
]
