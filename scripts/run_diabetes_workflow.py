#!/usr/bin/env python3
"""
Trigger Diabetes-Management-system workflow in Hive-Machine (local-only, local model).

- Installs workflow YAML to ~/.hive/machine/workflows/diabetes_management.yaml (3-tier)
- Ensures 3-tier workspace dirs
- Optionally places synthetic CareLink data if none exists
- Runs workflow via hive.machine.workflows.run_workflow with local Ollama model
- Prints report path and tail

Usage:
  python scripts/run_diabetes_workflow.py                 # sample data + local run
  python scripts/run_diabetes_workflow.py --no-sample
  python scripts/run_diabetes_workflow.py --input /path/to/CareLink.csv
  python scripts/run_diabetes_workflow.py --dry-run
"""
from __future__ import annotations
import argparse, sys, pathlib
from pathlib import Path

def ensure_sample(datasets: Path, force=False):
    if any(datasets.glob("*.csv")) and not force:
        return None
    datasets.mkdir(parents=True, exist_ok=True)
    sample = datasets / "carelink.csv"
    # reuse diabetes_carelink_report --sample
    import subprocess
    r = subprocess.run([sys.executable, "scripts/diabetes_carelink_report.py", "--sample", "--input", str(sample)], capture_output=True, text=True)
    print(r.stdout)
    if r.stderr:
        print(r.stderr, file=sys.stderr)
    return sample

def main():
    ap = argparse.ArgumentParser(description="Run Diabetes-Management-system workflow (local model)")
    ap.add_argument("--input", type=Path, default=None, help="CareLink CSV to place into workspace (optional)")
    ap.add_argument("--no-sample", action="store_true", help="do not generate synthetic sample if no CSV exists")
    ap.add_argument("--dry-run", action="store_true", help="dry run without executing tools/LLM")
    ap.add_argument("--workflow", default="diabetes_management", help="workflow name")
    args = ap.parse_args()

    from hive.config import load_config
    from hive.machine import WORKFLOWS_DIR, MACHINE_DIR
    from hive.machine.workflows import save_workflow, run_workflow, DIABETES_MANAGEMENT, list_workflows
    from hive.machine import workflow_base

    # install workflow definition
    save_workflow(args.workflow, DIABETES_MANAGEMENT)
    print(f"Workflow saved: {WORKFLOWS_DIR / (args.workflow + '.yaml')}")
    print(f"Available workflows: {[p.stem for p in list_workflows()]}")

    ws_base = workflow_base(args.workflow)
    ws_local = ws_base / "local-only"
    datasets = ws_local / "datasets"
    reports = ws_local / "reports"
    datasets.mkdir(parents=True, exist_ok=True)
    reports.mkdir(parents=True, exist_ok=True)

    # handle input CSV
    if args.input:
        if not args.input.exists():
            print(f"[error] --input not found: {args.input}", file=sys.stderr)
            sys.exit(1)
        import shutil
        dest = datasets / "carelink.csv"
        shutil.copy(args.input, dest)
        print(f"Placed CareLink CSV: {args.input} -> {dest} ({dest.stat().st_size} bytes)")
    elif not any(datasets.glob("*.csv")) and not args.no_sample:
        print("No CareLink CSV found — generating synthetic sample…")
        ensure_sample(datasets)

    cfg = load_config()
    # Force local provider for this workflow (privacy)
    # Keep user config but ensure ollama is used; run_workflow's LLM step already pins ollama
    print(f"Running workflow '{args.workflow}' via local model (provider={cfg.llm.provider}, ollama={cfg.llm.ollama_model}) dry_run={args.dry_run}")
    result = run_workflow(args.workflow, cfg=cfg, dry_run=args.dry_run)
    print(f"\nWorkflow '{result['workflow']}' finished in {result['elapsed']:.1f}s")
    print(f"Outputs: {list(result['outputs'].keys())}")
    for k, v in result['outputs'].items():
        preview = v[:600] if isinstance(v, str) else str(v)[:600]
        print(f"\n--- {k} ---\n{preview}{'...' if len(v) > 600 else ''}")

    # report location (3-tier resolution uses workflow_id/tier/reports)
    # Our workflow writes to reports/carelink_report.md which maps to workspace/<wf>/local-only/reports/carelink_report.md
    report_path = ws_local / "reports" / "carelink_report.md"
    if report_path.exists():
        print(f"\nReport: {report_path} ({report_path.stat().st_size} bytes)")
        print(report_path.read_text()[:3000])
    else:
        # also check tiered mapping fallback
        alt = ws_base / "local-only" / "reports" / "carelink_report.md"
        print(f"Report not at expected primary; check {alt} exists={alt.exists()} workspace listing:")
        for p in sorted(ws_base.rglob("*")):
            print(f"  {p.relative_to(ws_base)}")

if __name__ == "__main__":
    main()
