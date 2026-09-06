from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.markdown import Markdown

from hive import __version__
from hive.config import load_config, save_config, AppConfig, CONFIG_FILE, DB_FILE
from hive.llm import ChatMessage, chat, chat_stream, get_provider
from hive.papers import openalex, arxiv, rank as rank_mod, resolver
from hive.research.workflows import search_and_rank, enrich_full_text, run_workflow
from hive.research.session import list_sessions

app = typer.Typer(add_completion=False, rich_markup_mode="markdown", help="Hive Research - A Local research companion (Ollama/LM Studio)")
console = Console()

# ── Hive-Machine sub-app (Perplexity Computer) ───────────────────────
machine_app = typer.Typer(help="Hive-Machine — local Perplexity Computer (files, code, web, terminal)", no_args_is_help=False)
app.add_typer(machine_app, name="machine")


# ── helpers ──────────────────────────────────────────────────────────

def _cfg() -> AppConfig:
    return load_config()


def _print_papers(papers, json_out: bool = False):
    if json_out:
        print(json.dumps([p.model_dump() for p in papers], indent=2, ensure_ascii=False))
        return
    t = Table(title="PaperRank", show_lines=False)
    t.add_column("#", style="dim", width=3)
    t.add_column("Score", justify="right", style="bold cyan")
    t.add_column("Title")
    t.add_column("Venue / Year", style="dim")
    t.add_column("Cites", justify="right")
    t.add_column("OA", justify="center")
    for i, p in enumerate(papers, 1):
        t.add_row(
            str(i),
            f"{p.score:.1f}" if p.score is not None else "-",
            (p.title[:80] + "…") if len(p.title) > 80 else p.title,
            f"{p.venue or '-'} {p.year or ''}",
            str(p.cited_by_count),
            "✓" if (p.is_open_access or p.oa_url) else "",
        )
    console.print(t)
    for p in papers:
        console.print(f"[dim]{p.url or p.doi or p.id}[/dim]")


# ── commands ─────────────────────────────────────────────────────────

@app.command("rank")
def rank_cmd(
    query: str = typer.Argument(..., help="Topic to rank, e.g. 'mechanistic interpretability sparse autoencoders'"),
    top_k: int = typer.Option(10, "--top", "-k", help="How many papers"),
    full_text_top: int = typer.Option(3, "--full-text-top", help="Fetch section-aware evidence for top N and rescore via LLM"),
    json_out: bool = typer.Option(False, "--json", help="JSON output"),
    no_llm: bool = typer.Option(False, "--no-llm", help="Skip LLM rescoring, deterministic ranking only"),
):
    """PaperRank scoring for deciding what to read first, with transparent evidence."""
    cfg = _cfg()
    papers = search_and_rank(query, top_k=top_k, cfg=cfg)
    if not papers:
        console.print("[yellow]No papers found[/yellow]")
        raise typer.Exit(1)

    # optional LLM rescoring with full-text evidence
    if full_text_top > 0 and not no_llm and len(papers) >= 1:
        prov = get_provider(cfg)
        ok, _ = prov.health()
        if ok:
            ft = enrich_full_text(papers, top_n=full_text_top)
            # build rescoring prompt
            from hive.research.prompts import RANK_RESCORING
            block = "\n".join(f"{p.id}: {p.title} score={p.score} bd={p.score_breakdown}" for p in papers)
            ft_block = "\n".join(f"{p.title}\n{(txt or '')[:4000]}" for p, txt in ft)
            prompt = RANK_RESCORING.format(topic=query, papers_block=block, fulltext_block=ft_block)
            try:
                resp = chat(cfg, [ChatMessage(role="system", content="You are a ranking assistant. Return JSON only."), ChatMessage(role="user", content=prompt)])
                # try parse rescoring; keep original if fails
                console.print(Markdown(f"**LLM rescoring evidence (top {full_text_top}):**\n\n{resp.content[:2000]}"))
            except Exception as e:
                console.print(f"[dim]LLM rescoring skipped: {e}[/dim]")
        else:
            console.print("[dim]No local LLM available — showing deterministic ranking only[/dim]")

    _print_papers(papers, json_out=json_out)
    if not json_out:
        # breakdown
        for p in papers:
            bd = p.score_breakdown or {}
            console.print(f"[dim]{p.title[:70]} → {bd}[/dim]")


@app.command("paper")
def paper_cmd(
    identifier: str = typer.Argument(..., help="DOI, arXiv ID, OpenAlex ID, or title"),
    fetch_full_text: bool = typer.Option(False, "--fetch-full-text", help="Resolve and fetch source-specific full text"),
    json_out: bool = typer.Option(False, "--json", help="JSON output"),
):
    """Paper access resolver — OpenAlex/arXiv/DOI/Europe PMC candidates + optional text fetch."""
    cfg = _cfg()
    p = resolver.resolve(identifier)
    if not p:
        console.print(f"[red]Could not resolve: {identifier}[/red]")
        raise typer.Exit(1)
    if json_out:
        print(json.dumps(p.model_dump(), indent=2, ensure_ascii=False))
    else:
        console.print(Markdown(f"# {p.title}\n\n**Authors:** {', '.join(p.authors) or '—'}  \n**Venue:** {p.venue or '—'} {p.year or ''}  \n**DOI:** {p.doi or '—'}  \n**URL:** {p.url or p.oa_url or p.pdf_url or '—'}  \n**Cited by:** {p.cited_by_count}  \n**OA:** {p.is_open_access}\n\n> {p.abstract or '(no abstract)'}"))
    if fetch_full_text:
        txt = resolver.fetch_full_text(p)
        if txt:
            if json_out:
                print(json.dumps({"full_text": txt[:30000]}))
            else:
                console.print(Markdown(f"## Full-text evidence\n\n{txt[:8000]}"))
        else:
            console.print("[yellow]No legal full-text available for this paper[/yellow]")


@app.command("ask")
def ask_cmd(
    question: str = typer.Argument(..., help="Natural language question"),
    stream: bool = typer.Option(True, "--stream/--no-stream", help="Stream tokens"),
):
    """Ask the local LLM directly (no paper search)."""
    cfg = _cfg()
    msgs = [ChatMessage(role="user", content=question)]
    prov = get_provider(cfg)
    ok, msg = prov.health()
    if not ok:
        console.print(f"[red]No local LLM reachable: {msg}\nCheck ollama serve or LM Studio (http://localhost:1234)[/red]")
        raise typer.Exit(1)
    if stream:
        for tok in chat_stream(cfg, msgs):
            print(tok, end="", flush=True)
        print()
    else:
        resp = chat(cfg, msgs)
        console.print(Markdown(resp.content))


def _workflow_cmd(kind: str, topic: str, top: int, full_text_top: int, no_stream: bool = False):
    cfg = _cfg()
    prov = get_provider(cfg)
    ok, msg = prov.health()
    if not ok:
        console.print(f"[red]No local LLM reachable: {msg}[/red]")
        raise typer.Exit(1)
    with console.status(f"[bold green]Running {kind} — local LLM ({prov.name})...[/bold green]"):
        out = run_workflow(kind, topic, cfg, top_k=top, full_text_top=full_text_top)
    console.print(Markdown(out))
    console.print(f"\n[dim]Saved to {DB_FILE} — view with: hive sessions[/dim]")


@app.command("deepresearch")
def deepresearch(query: str = typer.Argument(..., help="Topic"), top: int = typer.Option(10, "--top"), full_text_top: int = typer.Option(3, "--full-text-top")):
    """/deepresearch — source-heavy multi-agent investigation."""
    _workflow_cmd("deepresearch", query, top, full_text_top)

@app.command("lit")
def lit(query: str = typer.Argument(..., help="Topic or lab"), top: int = typer.Option(12, "--top"), full_text_top: int = typer.Option(3, "--full-text-top")):
    """/lit — literature review from paper search and primary sources."""
    _workflow_cmd("lit", query, top, full_text_top)

@app.command("review")
def review_cmd(artifact: str = typer.Argument(..., help="Artifact to review"), top: int = typer.Option(8, "--top"), full_text_top: int = typer.Option(2, "--full-text-top")):
    """/review — research review with severity and revision plan."""
    _workflow_cmd("review", artifact, top, full_text_top)

@app.command("audit")
def audit(item: str = typer.Argument(..., help="Paper vs codebase item"), top: int = typer.Option(8, "--top"), full_text_top: int = typer.Option(2, "--full-text-top")):
    """/audit — paper vs codebase mismatch audit."""
    _workflow_cmd("audit", item, top, full_text_top)

@app.command("replicate")
def replicate(paper: str = typer.Argument(..., help="Paper to replicate"), top: int = typer.Option(8, "--top"), full_text_top: int = typer.Option(3, "--full-text-top")):
    """/replicate — plan replication checks (execute only after choosing env)."""
    _workflow_cmd("replicate", paper, top, full_text_top)

@app.command("recipe")
def recipe(task: str = typer.Argument(..., help="Task or paper"), top: int = typer.Option(10, "--top"), full_text_top: int = typer.Option(2, "--full-text-top")):
    """/recipe — ranked ML training recipes."""
    _workflow_cmd("recipe", task, top, full_text_top)

@app.command("compare")
def compare(topic: str = typer.Argument(..., help="Topic"), top: int = typer.Option(10, "--top"), full_text_top: int = typer.Option(3, "--full-text-top")):
    """/compare — source comparison matrix."""
    _workflow_cmd("compare", topic, top, full_text_top)

@app.command("draft")
def draft(topic: str = typer.Argument(..., help="Topic"), top: int = typer.Option(10, "--top"), full_text_top: int = typer.Option(3, "--full-text-top")):
    """/draft — paper-style draft from research findings."""
    _workflow_cmd("draft", topic, top, full_text_top)

@app.command("autoresearch")
def autoresearch(idea: str = typer.Argument(..., help="Idea"), top: int = typer.Option(8, "--top"), full_text_top: int = typer.Option(2, "--full-text-top")):
    """/autoresearch — bounded experiment loop with benchmark evidence."""
    _workflow_cmd("autoresearch", idea, top, full_text_top)

@app.command("watch")
def watch(topic: str = typer.Argument(..., help="Topic"), top: int = typer.Option(10, "--top"), full_text_top: int = typer.Option(2, "--full-text-top")):
    """/watch — research watch baseline with optional scheduled follow-up."""
    _workflow_cmd("watch", topic, top, full_text_top)


@app.command("report")
def report_cmd(
    topic: str = typer.Argument(..., help="Topic for deep analysis report"),
    top: int = typer.Option(12, "--top", help="Papers to ground on"),
    full_text_top: int = typer.Option(3, "--full-text-top", help="Full-text evidence count"),
    depth: str = typer.Option("deep", "--depth", help="brief|standard|deep"),
    no_save: bool = typer.Option(False, "--no-save", help="Don't persist to DB/workspace"),
):
    """Deep analysis report — 20-section Feynman-parity report (hero, provenance, synthesis, matrix, checklist, lineage, changelog) — local only."""
    cfg = _cfg()
    prov = get_provider(cfg)
    ok, msg = prov.health()
    if not ok:
        console.print(f"[red]No local LLM reachable: {msg}[/red]")
        raise typer.Exit(1)
    from hive.research.report import generate_deep_report
    with console.status(f"[bold green]Deep Report — {topic} via {prov.name} (top={top}, depth={depth})...[/bold green]"):
        md, sid, aid = generate_deep_report(topic, cfg, top_k=top, full_text_top=full_text_top, depth=depth, save=not no_save)
    console.print(Markdown(md))
    if not no_save:
        console.print(f"\n[dim]Saved artifact {aid} session {sid} → ~/.hive/machine/workspace/report_{sid}.md — hive sessions[/dim]")


@app.command("tui")
def tui_cmd():
    """Launch Hive Research - A Local research companion — terminal workbench (local, Ollama/LM Studio)."""
    try:
        from hive.tui.app import run
    except ImportError as e:
        console.print(f"[red]TUI requires textual: {e}\nInstall: pip install textual  or  pip install -e \".[tui]\"[/red]")
        raise typer.Exit(1)
    run()


# ── Hive-Machine commands ──────────────────────────────────────────

@machine_app.command("run")
def machine_run(
    task: str = typer.Argument(..., help="Task for Hive-Machine, e.g. 'fetch https://example.com and summarize to report.md'"),
    steps: int = typer.Option(12, "--steps", "-n", help="Max agent steps"),
):
    """Run Hive-Machine agent headlessly (no TUI) — local computer use."""
    from hive.machine.agent import run_task
    from hive.machine import WORKSPACE
    cfg = _cfg()
    console.print(f"[bold cyan]Hive-Machine: {task}[/bold cyan]  [dim]max_steps={steps} ws={WORKSPACE}[/dim]")
    out = run_task(task, cfg, max_steps=steps, verbose=False)
    console.print(Markdown(out))


@machine_app.command("tui")
def machine_tui():
    """Launch Hive-Machine TUI — local Perplexity Computer."""
    try:
        from hive.machine.app import run as mrun
    except ImportError as e:
        console.print(f"[red]Hive-Machine TUI requires textual: {e}[/red]")
        raise typer.Exit(1)
    mrun()


@machine_app.command("ls")
def machine_ls(
    path: str = typer.Argument(".", help="Path relative to workspace ~/.hive/machine/workspace"),
    recursive: bool = typer.Option(False, "--recursive", "-r", help="Recursive"),
):
    """List workspace files (jailed)."""
    from hive.machine.tools import list_files
    console.print(list_files(path, recursive))


@machine_app.command("read")
def machine_read(path: str = typer.Argument(..., help="File to read (relative to workspace)")):
    """Read a workspace file."""
    from hive.machine.tools import read_file
    console.print(read_file(path))


@machine_app.command("write")
def machine_write(
    path: str = typer.Argument(..., help="Destination relative to workspace"),
    content: str = typer.Argument(..., help="Content to write"),
):
    """Write a workspace file."""
    from hive.machine.tools import write_file
    console.print(write_file(path, content))


@machine_app.command("exec")
def machine_exec(
    cmd: str = typer.Option(..., "--cmd", "-c", help="Bash command to run in workspace"),
    timeout: int = typer.Option(30, "--timeout"),
):
    """Run bash in Hive-Machine workspace."""
    from hive.machine.tools import run_bash
    console.print(run_bash(cmd, timeout))


@machine_app.command("python")
def machine_python(
    code: str = typer.Option(..., "--code", "-c", help="Python code to run"),
    timeout: int = typer.Option(30, "--timeout"),
):
    """Run python snippet in workspace."""
    from hive.machine.tools import run_python
    console.print(run_python(code, timeout))


@machine_app.command("fetch")
def machine_fetch(url: str = typer.Argument(..., help="URL to fetch")):
    """Web fetch via Hive-Machine (local httpx + BS4)."""
    from hive.machine.tools import web_fetch
    console.print(web_fetch(url)[:8000])


@machine_app.command("search")
def machine_search(query: str = typer.Argument(..., help="Search query (OpenAlex)"), top: int = typer.Option(5, "--top")):
    """Web/paper search via Hive-Machine."""
    from hive.machine.tools import web_search
    console.print(web_search(query, top))


@machine_app.command("history")
def machine_history(limit: int = typer.Option(20, "--limit", "-n")):
    """Show Hive-Machine run history."""
    from hive.machine.agent import list_history
    rows = list_history(limit)
    if not rows:
        console.print("[dim]No machine runs yet[/dim]")
        return
    t = Table()
    t.add_column("ID")
    t.add_column("Task")
    t.add_column("Steps")
    t.add_column("Created")
    import datetime
    for rid, task, created, steps in rows:
        dt = datetime.datetime.fromtimestamp(created).strftime("%Y-%m-%d %H:%M") if created else ""
        t.add_row(str(rid), task[:60], str(steps), dt)
    console.print(t)


@machine_app.callback(invoke_without_command=True)
def machine_callback(ctx: typer.Context):
    """Hive-Machine — local Perplexity Computer. No args → launch TUI."""
    if ctx.invoked_subcommand is None:
        try:
            from hive.machine.app import run as mrun
        except ImportError as e:
            console.print(f"[red]Hive-Machine TUI requires textual: {e}[/red]")
            raise typer.Exit(1)
        mrun()


@app.command("serve")
def serve(host: str = typer.Option("127.0.0.1", "--host"), port: int = typer.Option(8000, "--port"), no_auth: bool = typer.Option(False, "--no-auth", help="Plain localhost mode")):
    """Open a minimal local workbench (static preview of sessions/artifacts)."""
    from http.server import HTTPServer, SimpleHTTPRequestHandler
    import sqlite3
    console.print(f"[green]Hive workbench at http://{host}:{port} — sessions in {DB_FILE}[/green]")
    console.print("[dim]This is a minimal preview; full workbench UI is available via Open WebUI integration (see openwebui/README.md)[/dim]")
    # quick dump
    for sid, topic, ts in list_sessions():
        console.print(f"  {sid}  {topic}")
    # simple file server for artifacts exported to ~/.hive/exports (if exists)
    exports = Path.home() / ".hive" / "exports"
    exports.mkdir(parents=True, exist_ok=True)
    import os
    os.chdir(exports)
    httpd = HTTPServer((host, port), SimpleHTTPRequestHandler)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped[/dim]")


@app.command("config")
def config_cmd(
    show: bool = typer.Option(False, "--show", help="Show current config"),
    provider: Optional[str] = typer.Option(None, "--provider", help="ollama | lmstudio | auto"),
    ollama_url: Optional[str] = typer.Option(None, "--ollama-url"),
    ollama_model: Optional[str] = typer.Option(None, "--ollama-model"),
    lmstudio_url: Optional[str] = typer.Option(None, "--lmstudio-url"),
    lmstudio_model: Optional[str] = typer.Option(None, "--lmstudio-model"),
):
    """View or set local-LLM config (~/.hive/config.toml)."""
    cfg = _cfg()
    changed = False
    if provider:
        cfg.llm.provider = provider  # type: ignore
        changed = True
    if ollama_url:
        cfg.llm.ollama_url = ollama_url
        changed = True
    if ollama_model:
        cfg.llm.ollama_model = ollama_model
        changed = True
    if lmstudio_url:
        cfg.llm.lmstudio_url = lmstudio_url
        changed = True
    if lmstudio_model:
        cfg.llm.lmstudio_model = lmstudio_model
        changed = True
    if changed:
        save_config(cfg)
        console.print(f"[green]Saved to {CONFIG_FILE}[/green]")
    console.print(json.dumps({"provider": cfg.llm.provider, "ollama_url": cfg.llm.ollama_url, "ollama_model": cfg.llm.ollama_model, "lmstudio_url": cfg.llm.lmstudio_url, "lmstudio_model": cfg.llm.lmstudio_model, "config_file": str(CONFIG_FILE)}, indent=2))


@app.command("models")
def models_cmd():
    """List local models (Ollama + LM Studio)."""
    cfg = _cfg()
    for name, prov in [
        ("ollama", __import__("hive.llm.ollama", fromlist=["OllamaProvider"]).OllamaProvider(cfg.llm.ollama_url, cfg.llm.ollama_model)),
        ("lmstudio", __import__("hive.llm.lmstudio", fromlist=["LMStudioProvider"]).LMStudioProvider(cfg.llm.lmstudio_url, cfg.llm.lmstudio_model)),
    ]:
        ok, msg = prov.health()
        if ok:
            try:
                ms = prov.list_models()
                console.print(f"[green]{name} ({prov.base_url}):[/green] {', '.join(ms) or '(no models)'}")
            except Exception as e:
                console.print(f"[yellow]{name}: {e}[/yellow]")
        else:
            console.print(f"[dim]{name} not reachable at {prov.base_url}: {msg}[/dim]")


@app.command("sessions")
def sessions_cmd(limit: int = typer.Option(20, "--limit", "-n")):
    """Browse research artifacts (like /outputs)."""
    rows = list_sessions(limit=limit)
    if not rows:
        console.print("[dim]No sessions yet[/dim]")
        return
    t = Table()
    t.add_column("ID")
    t.add_column("Topic")
    t.add_column("Created")
    import datetime
    for sid, topic, ts in rows:
        dt = datetime.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else ""
        t.add_row(sid, topic, dt)
    console.print(t)


@app.command("doctor")
def doctor():
    """Diagnose local LLM + paper APIs."""
    cfg = _cfg()
    console.print(f"[bold]Config:[/bold] {CONFIG_FILE}  provider={cfg.llm.provider}")
    for label, prov in [
        ("Ollama", __import__("hive.llm.ollama", fromlist=["OllamaProvider"]).OllamaProvider(cfg.llm.ollama_url, cfg.llm.ollama_model)),
        ("LM Studio", __import__("hive.llm.lmstudio", fromlist=["LMStudioProvider"]).LMStudioProvider(cfg.llm.lmstudio_url, cfg.llm.lmstudio_model)),
    ]:
        ok, msg = prov.health()
        console.print(f"  {label} @ {prov.base_url}: {'[green]ok[/green]' if ok else f'[red]{msg}[/red]'}")
    # paper APIs
    import httpx
    for name, url in [("OpenAlex", "https://api.openalex.org/works?search=test&per-page=1"), ("arXiv", "https://export.arxiv.org/api/query?search_query=all:test&max_results=1")]:
        try:
            with httpx.Client(timeout=8) as c:
                r = c.get(url)
                console.print(f"  {name}: {'[green]ok[/green]' if r.status_code==200 else f'[red]{r.status_code}[/red]'}")
        except Exception as e:
            console.print(f"  {name}: [red]{e}[/red]")


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context, version: bool = typer.Option(False, "--version", help="Show version")):
    if version:
        console.print(f"hive-research {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        # interactive REPL
        console.print(Markdown(f"# Hive Research - A Local research companion {__version__}\nLocal research companion — Ollama / LM Studio only.\n\nType a question, or `help` for commands. `exit` to quit.\nTry `hive tui` for full terminal workbench.\n"))
        cfg = _cfg()
        prov = get_provider(cfg)
        ok, msg = prov.health()
        console.print(f"[dim]LLM: {prov.name} @ {prov.base_url} — {'ok' if ok else msg}[/dim]")
        console.print("[dim]Commands: rank <topic> | paper <id> | /deepresearch <topic> | /lit | /review | /compare | /draft | ask <q> | doctor | tui[/dim]\n")
        while True:
            try:
                q = typer.prompt("hive>")
            except (EOFError, KeyboardInterrupt):
                break
            if not q.strip():
                continue
            if q.strip() in ("exit", "quit", "/exit"):
                break
            if q.strip() in ("help", "/help", "?"):
                console.print("[dim]Commands: rank, paper, deepresearch, lit, review, audit, replicate, recipe, compare, draft, autoresearch, watch, ask, doctor, models, sessions, config[/dim]")
                continue
            # parse slash commands
            if q.startswith("/"):
                parts = q[1:].split(maxsplit=1)
                kind = parts[0]
                topic = parts[1] if len(parts) > 1 else typer.prompt(f"{kind} topic")
                try:
                    _workflow_cmd(kind, topic, top=10, full_text_top=3)
                except SystemExit:
                    pass
                except Exception as e:
                    console.print(f"[red]{e}[/red]")
                continue
            if q.startswith("rank "):
                try:
                    rank_cmd(q[5:], top_k=10, full_text_top=3, json_out=False, no_llm=False)  # type: ignore
                except SystemExit:
                    pass
                continue
            if q.startswith("paper "):
                try:
                    paper_cmd(q[6:], fetch_full_text=False, json_out=False)  # type: ignore
                except SystemExit:
                    pass
                continue
            # default: ask LLM with paper context
            try:
                for tok in chat_stream(cfg, [ChatMessage(role="user", content=q)]):
                    print(tok, end="", flush=True)
                print()
            except Exception as e:
                console.print(f"[red]{e}[/red]")


if __name__ == "__main__":
    app()
