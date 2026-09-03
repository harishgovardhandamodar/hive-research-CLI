# Hive Research — Detailed Documentation

> **Local-only Feynman clone** — every LLM call runs through **Ollama** or **LM Studio**. No cloud keys. Papers via public APIs (OpenAlex / arXiv / Crossref / Europe PMC). CLI + TUI workbench + Open WebUI integration.

Version: `0.1.0` · Python `>=3.10` · License: MIT (Feynman © companion-inc/feynman)

---

## Table of Contents

1. [Overview & Goals](#1-overview--goals)
2. [Architecture](#2-architecture)
3. [Installation](#3-installation)
4. [Configuration](#4-configuration)
5. [CLI Reference](#5-cli-reference)
6. [TUI Workbench](#6-tui-workbench)
6b. [Hive-Machine — Perplexity Computer](#6b-hive-machine--perplexity-computer-local)
7. [Paper System](#7-paper-system)
8. [Research Workflows](#8-research-workflows)
9. [Open WebUI Integration](#9-open-webui-integration)
10. [Data & Provenance](#10-data--provenance)
11. [Development](#11-development)
12. [Troubleshooting](#12-troubleshooting)
13. [Roadmap & Limitations](#13-roadmap--limitations)
14. [License](#14-license)

---

## 1. Overview & Goals

Hive Research re-implements Feynman feature-by-feature but **removes all cloud dependencies**:

| Feynman (original) | Hive (this repo) |
|---|---|
| `feynman rank <topic> --full-text-top 3` | `hive rank <topic> --full-text-top 3` — same scoring, section-aware full-text, LLM rescoring via local model |
| `feynman paper <id> --fetch-full-text` | `hive paper <id> --fetch-full-text` — OpenAlex / arXiv / Crossref / Europe PMC resolver |
| `feynman serve` (science workbench) | `hive serve` (minimal HTTP preview) + `hive tui` (full Textual workbench) |
| `/deepresearch`, `/lit`, `/review`, `/audit`, `/replicate`, `/recipe`, `/compare`, `/draft`, `/autoresearch`, `/watch`, `/thinking`, `/outputs` | `hive deepresearch/lit/review/...` + same slash commands in REPL and TUI + `hive sessions` |
| Pi agent runtime, Modal/RunPod, PostHog | Pure Python, no cloud, `~/.hive/hive.db` |
| AlphaXiv, BioTools (100+), HF Hub | OpenAlex + arXiv (primary), Crossref + Europe PMC (full-text); extensible `hive/papers/` |
| Hosted LLM providers | **Ollama** `http://localhost:11434/api/chat` and **LM Studio** `http://localhost:1234/v1/chat/completions` (OpenAI-compatible), auto-detect |

**Invariant:** every synthesis is **source-grounded** — title, venue, DOI/URL, citation counts are shown and persisted.

---

## 2. Architecture

### 2.1 Module map (`hive/`)

```
hive/
  __init__.py          # __version__ = "0.1.0"
  config.py            # AppConfig / LLMConfig, ~/.hive/config.toml + env overrides
  cli.py               # Typer app: hive / hive-research entry point, REPL, doctor, serve
  tui/
    app.py             # HiveTUI (Textual) — menu, RichLog, threaded workers
  llm/
    base.py            # ChatMessage, ChatResponse, LLMProvider abstract
    ollama.py          # OllamaProvider — /api/tags, /api/chat (streaming, fallback model)
    lmstudio.py        # LMStudioProvider — /v1/models, /v1/chat/completions
    client.py          # get_provider(auto), chat(), chat_stream() with 404 fallback
  papers/
    schemas.py         # Paper (Pydantic): id/title/authors/abstract/venue/year/doi/arxiv/citations/OA/score
    openalex.py        # OpenAlex /works search + abstract_inverted_index → text
    arxiv.py           # arXiv export API (https) via feedparser
    crossref.py        # Crossref /works/{doi}
    europe_pmc.py      # Europe PMC search + fullTextXML → sections
    rank.py            # rank_papers() deterministic PaperRank 0–100
    resolver.py        # resolve(DOI/arXiv/OpenAlex/title) + fetch_full_text()
  research/
    prompts.py         # SYSTEM + templates for each workflow + RANK_RESCORING
    workflows.py       # search_and_rank(), enrich_full_text(), run_workflow(kind, topic)
    session.py         # SQLite helpers: new_session(), save_artifact(), list_sessions()
  utils/
    rich.py            # Rich console helpers
openwebui/
  hive_tools.py        # Open WebUI Tools (13 tools, Valves)
  hive_pipe.py         # Open WebUI Pipe (auto-inject for non-tool models)
  README.md            # Docker networking, Valves reference
```

Build: `pyproject.toml:1` (`hatchling`, `packages = ["hive", "openwebui"]`, scripts `hive` + `hive-research`).

### 2.2 Data flow

```
User: "sparse autoencoders" 
  → hive/papers/openalex.search() (+ arxiv fallback)
  → hive/papers/rank.rank_papers()  # citations, recency, venue, OA, abstract, query_match
  → hive/papers/resolver.fetch_full_text()  # Europe PMC XML → sections (top 3)
  → hive/llm/client.chat() → Ollama or LM Studio (health-checked, 404 fallback)
  → hive/research/prompts.RANK_RESCORING / DEEP_RESEARCH etc.
  → hive/research/session.save_artifact() → ~/.hive/hive.db
  → Rich table / Markdown (CLI) or RichLog (TUI) or Tool return (Open WebUI)
```

### 2.3 LLM routing (`hive/config.py:32`, `hive/llm/client.py:1`)

```python
# config.py defaults
LLMConfig(provider="auto", ollama_url="http://localhost:11434",
          ollama_model="llama3.1:8b", lmstudio_url="http://localhost:1234/v1",
          lmstudio_model="qwen/qwen3.8-27b")

# client.py
get_provider(cfg): 
  if cfg.llm.provider == "ollama": return OllamaProvider(...)
  if == "lmstudio": return LMStudioProvider(...)
  if == "auto":     health Ollama → else LM Studio → else Ollama (error surfaced by caller)
chat()/chat_stream(): on 404/not found → _fallback_model() (list_models, base-name match, first available)
```

Both providers implement `ChatMessage`, `chat()`, `chat_stream()`, `list_models()`, `health()`.

### 2.4 Ranking (`hive/papers/rank.py:1`)

Deterministic + transparent, then optional LLM rescoring with full-text:

- citations: `10*log10(c+1)` capped 30
- venue: 12 if peer-reviewed, 5 if arXiv, 0 else
- recency: `10 - age*0.7` (2026 baseline)
- open_access: 10 if OA / pdf_url / oa_url
- abstract_quality: 5 if >100 chars
- query_match: up to 30 (token hits in title+abstract)

`score_paper()` returns `(score, breakdown)`; `rank_papers()` sorts descending. LLM step (`RANK_RESCORING` prompt) refines to 0–100 across methods-transparency / reproducibility / provenance / query-fit using section evidence.

### 2.5 Persistence (`hive/research/session.py:1`)

SQLite `~/.hive/hive.db`:
```sql
sessions(id TEXT PK, topic TEXT, created_at REAL, updated_at REAL, summary TEXT)
artifacts(id TEXT PK, session_id FK, kind TEXT, title TEXT, content TEXT, created_at REAL)
```
`~/.hive/exports/` for `hive serve` static preview; `~/.hive/config.toml` for LLM config.

---

## 3. Installation

### 3.1 Prerequisites

- Python 3.10+ (`python --version`)
- **One** local LLM (both can coexist):
  - **Ollama** — https://ollama.com : `ollama serve` (keeps running), then `ollama pull llama3.1:8b` (or `qwen3.8:27b-mlx`, `mistral`, `deepseek-r1:32b`, etc.). Verify `curl http://localhost:11434/api/tags | jq`.
  - **LM Studio** — https://lmstudio.ai : Open App → *Local Server* → *Start Server* (default `http://localhost:1234/v1`). Load a model (e.g. `qwen/qwen3.8-27b`), verify `curl http://localhost:1234/v1/models | jq`.

> LM Studio models appear as `qwen/qwen3.8-27b`, `qwen3.8-27b-uncensored-mlx`, etc. Use the exact `id` in config.

### 3.2 Install Hive

```bash
git clone https://github.com/harishgovardhandamodar/hive-research-CLI
cd hive-research-CLI
pip install -e .                 # CLI + TUI (textual included)
# or: pip install -e ".[tui]"  # TUI extra (textual)
# or: uv pip install -e .

# dev + tests
pip install -e ".[dev]"         # pytest, pytest-asyncio
pytest -q                       # 8 tests
```

Check:

```bash
hive --version          # 0.1.0
hive --help             # lists rank/paper/ask/deepresearch/lit/compare/review/audit/replicate/recipe/draft/autoresearch/watch/tui/serve/config/models/sessions/doctor
hive doctor             # Ollama ok, LM Studio ok, OpenAlex ok, arXiv ok
hive models             # lists local models per provider
hive tui --help         # TUI help
```

No cloud env vars needed.

### 3.3 Docker (optional, for parity)

```bash
docker build -t hive-research .
docker run --network=host -v ~/.hive:/root/.hive hive-research rank "transformer" --no-llm
# Open WebUI in Docker needs --add-host=host.docker.internal:host-gateway (see §9)
```

---

## 4. Configuration

**Precedence:** `~/.hive/config.toml` (written by `hive config`) < `env` overrides.

| Source | Key | Default | Env |
|---|---|---|---|
| `llm.provider` | `auto` / `ollama` / `lmstudio` | `auto` | `HIVE_PROVIDER` |
| `llm.ollama_url` | `http://localhost:11434` | `OLLAMA_BASE_URL` / `OLLAMA_URL` |
| `llm.ollama_model` | `llama3.1:8b` | `HIVE_OLLAMA_MODEL` |
| `llm.lmstudio_url` | `http://localhost:1234/v1` | `LMSTUDIO_BASE_URL` / `LMSTUDIO_URL` |
| `llm.lmstudio_model` | `qwen/qwen3.8-27b` | `HIVE_LMSTUDIO_MODEL` |
| `llm.temperature` | `0.3` | `HIVE_TEMPERATURE` |
| `llm.max_tokens` | `4096` | `HIVE_MAX_TOKENS` |
| `default_top_k` | `10` | `HIVE_TOP_K` |
| `full_text_top` | `3` | `HIVE_FULLTEXT_TOP` |

**Examples:**

```bash
hive config --show
hive config --provider ollama --ollama-model deepseek-r1:32b
hive config --provider lmstudio --lmstudio-model qwen3.8-27b-uncensored-mlx
hive config --ollama-url http://host.docker.internal:11434

# one-off env
HIVE_PROVIDER=ollama HIVE_OLLAMA_MODEL=llama3.1:8b hive ask "hi" --no-stream

# file
cat ~/.hive/config.toml
# [llm]
# provider = "auto"
# ollama_model = "llama3.1:8b"
# lmstudio_model = "qwen/qwen3.8-27b"

# .env.example is a template: cp .env.example .env
```

**Model fallback:** if the configured model 404s, `hive/llm/client.py:30` lists available models and retries with base-name match (`llama3.1` → `llama3.1:8b`) or first model, so `hive ask` rarely needs manual fix.

---

## 5. CLI Reference

All commands are `hive <cmd>` and `hive-research <cmd>` (alias). `hive` with no args enters REPL.

### 5.1 `rank` — PaperRank

```bash
hive rank "mechanistic interpretability sparse autoencoders" --top 10 --full-text-top 3
hive rank "diffusion models" --top 5 --no-llm --json > ranked.json
```

- Searches OpenAlex (`search` sort `relevance_score:desc`, `per-page=top`), falls back to arXiv if needed.
- Prints Rich table (Score, Title, Venue/Year, Cites, OA) + URLs + `score_breakdown` dict.
- With `--full-text-top 3` (default 3) and healthy local LLM: fetches Europe PMC sections for top 3, runs `RANK_RESCORING` prompt, prints LLM JSON + justification before table.
- `--no-llm` forces deterministic only (offline-friendly).

### 5.2 `paper` — resolver

```bash
hive paper 10.7717/peerj.4375
hive paper 10.7717/peerj.4375 --fetch-full-text
hive paper 2301.12345
hive paper "Attention is all you need" --json
```

- `hive/papers/resolver.py:1` detects DOI (`10.`), arXiv (`\d{4}\.\d{4}` / `arxiv`), OpenAlex `W\d+` / URL, else title search.
- Tries `openalex.fetch_by_doi` → `crossref.fetch_by_doi` for DOI; `arxiv.fetch` for arXiv; `openalex.fetch_by_id` for OpenAlex.
- `--fetch-full-text` → `resolver.fetch_full_text()`: Europe PMC XML if `doi` OA, else `oa_url` HTML truncated to 30k chars.
- `--json` emits `Paper` JSON (including `full_text` when fetched).

### 5.3 `ask` — direct chat

```bash
hive ask "Explain PaperRank transparently" --stream
hive ask "What is 2+2?" --no-stream
```

- Bypasses paper search; streams via `chat_stream()` (Ollama NDJSON, LM Studio SSE).

### 5.4 Research workflows

Each runs: `search_and_rank(topic, top)` → `enrich_full_text(papers, top_n=full_text_top)` → prompt template (`hive/research/prompts.py:1`) → `chat()` → `save_artifact()`.

```bash
hive deepresearch "test-time scaling for LLM reasoning" --top 12 --full-text-top 3
hive lit "NeurIPS 2024 best papers on retrieval" --top 12
hive compare "RLHF vs DPO" --top 8
hive review "paste artifact or description"
hive audit "paper + codebase notes"
hive replicate "10.1234/..." --top 8
hive recipe "fine-tune 7B on code" --top 10
hive draft "survey on synthetic data for code" --top 10
hive autoresearch "small-model self-correction loop" --top 8
hive watch "new sparse coding papers" --top 10
```

Output is Markdown (Rich), saved to `~/.hive/hive.db` (`hive sessions`).

### 5.5 Utility

```bash
hive serve --host 127.0.0.1 --port 8000  # HTTP preview of ~/.hive/exports + session dump
hive sessions --limit 20                 # like Feynman /outputs
hive doctor                              # LLM + OpenAlex + arXiv health
hive models                              # list per-provider models
hive config --show
hive config --provider auto
```

### 5.6 REPL (`hive` with no args)

```
Hive Research 0.1.0 … Try `hive tui` for full terminal workbench.
LLM: ollama@http://localhost:11434 ✓
Commands: rank <topic> | paper <id> | /deepresearch <topic> | ...

hive> /deepresearch mechanistic interpretability
hive> rank sparse autoencoders
hive> paper 10.1038/s41586-023-00000-0 --fetch-full-text
hive> Explain DPO vs RLHF   # default ask with streaming
hive> help / exit
```

Supports `/<workflow> <topic>`, `rank ...`, `paper ...`, else `chat_stream`.

---

## 6. TUI Workbench

Feynman-like terminal app, implemented with **Textual** (`hive/tui/app.py:1`).

### 6.1 Launch

```bash
hive tui
# install if needed: pip install textual  or  pip install -e ".[tui]"
```

### 6.2 Layout (`hive/tui/app.py:50`)

```
┌─ Header (Hive Research — local Feynman clone, clock) ─┐
├─ Menu (28 cols) │ Content                            │
│  Workflows      │  HELP_TEXT / RichLog output        │
│  Rank papers    │  (markdown, tables, LLM streams)   │
│  Paper lookup   │                                    │
│  Ask LLM        │  ┌─ Query input ─┬─ top ─┬─ Run ─┐ │
│  /deepresearch  │  └───────────────┴───────┴────────┘ │
│  ...            │  Status: LLM: ollama@... ✓ cfg: ... │
├─ Footer (keybindings) ────────────────────────────────┤
```

- CSS `hive/tui/app.py:52` — `Screen` vertical, `#menu` border tall `$primary`, `#output` border tall `$secondary`.
- Menu built as `ListView(*[ListItem(Label(label), id=menu-key) ...])` `hive/tui/app.py:86` (required: no `append` pre-mount).

### 6.3 Interactions

- **Select workflow**: click left menu or `1`–`9` (focus menu, press Enter). `sessions` / `doctor` run immediately; others show `Mode: <kind> — enter query`.
- **Run**: type topic/DOI/question in `#query` (`hive/tui/app.py:95`, placeholder `sparse autoencoders`), `top` in `#topk` (default 10), press **Enter** or **Run** `hive/tui/app.py:129`.
- **Dispatch** `hive/tui/app.py:151`: validates, logs `▶ kind: query`, calls threaded worker:
  - `rank` → `_run_rank` `hive/tui/app.py:180`: `search_and_rank` + table lines + optional LLM rescoring (full-text top 3 via `RANK_RESCORING`).
  - `paper` → `_run_paper` `hive/tui/app.py:212`: `resolver.resolve` + `fetch_full_text`.
  - `ask` → `_run_ask` `hive/tui/app.py:227`: `chat`.
  - others → `_run_workflow` `hive/tui/app.py:241`: `run_workflow(kind, topic, top_k, full_text_top)` with `call_from_thread` for safety.
- **Sessions** `hive/tui/app.py:255`: `list_sessions(30)` → bullet list with `id`, `topic`, `datetime`.
- **Doctor** `hive/tui/app.py:271`: config, `list_models` per provider, `httpx` checks for OpenAlex/arXiv.

All workers use `@work(thread=True)` + `call_from_thread(output.write)` to avoid blocking UI.

### 6.4 Keybindings (`hive/tui/app.py:67`)

| Key | Action |
|---|---|
| `q` | quit |
| `f` | focus input |
| `s` | show sessions (→ Sessions mode) |
| `d` | show doctor |
| `?` | help (writes `HELP_TEXT` `hive/tui/app.py:41`) |
| `Enter` (in query) | run |
| Mouse | menu select, Run button |

Help text `hive/tui/app.py:41` explains mode, input, persistence.

---

## 6b. Hive-Machine — Perplexity Computer (local)

Perplexity Computer parity, local-only. Hive-Machine gives the local LLM a **sandboxed computer**: file workspace, bash/python, web, terminal. No cloud, no browser automation, just `~/.hive/machine/workspace` jailed.

### 6b.1 Architecture (`hive/machine/`)

```
hive/machine/
  __init__.py  # MACHINE_DIR=~/.hive/machine, WORKSPACE=.../workspace, HISTORY_DB=.../machine.db
  tools.py     # 8 tools + _jail() sandbox, TOOL_SCHEMAS, DISPATCH, dispatch_tool()
  agent.py     # SYSTEM prompt, _extract_tool (```json {"tool": ...}```), run_task(task, cfg, max_steps=12), save_run(), list_history()
  app.py       # HiveMachineApp (Textual) — file tree, RichLog center, preview right, Input
```

**Sandbox** `hive/machine/tools.py:15` `_jail(path)`: `WORKSPACE / Path(path).resolve()` must start with `WORKSPACE.resolve()`, else `ValueError` — prevents `..` / absolute escape. Every file/code op uses `_jail`.

**DB** `hive/machine/__init__.py:8` `~/.hive/machine/machine.db` `runs(id, task, created, steps, final)` — `agent.py:20` `_init_db()` / `save_run()`.

### 6b.2 Tools (8) `hive/machine/tools.py:45`

| Tool | Args | Impl |
|---|---|---|
| `list_files` | `path=".", recursive=false` | `_jail(path).glob("*"/"**/*")` → `rel  [dir/file N B]` (cap 200) |
| `read_file` | `path, max_bytes=50000` | `_jail(path).read_bytes()[:max]` → utf-8 or `[binary … hex]` |
| `write_file` | `path, content` | `_jail(path).parent.mkdir` → `write_text` → `wrote N chars → path` |
| `delete_path` | `path` | `_jail(path)` → `shutil.rmtree` or `unlink` |
| `run_bash` | `cmd, timeout=30` | `subprocess.run(shell=True, cwd=WORKSPACE, capture_output, timeout)` → `exit code + stdout/stderr` (20k cap) |
| `run_python` | `code, timeout=30` | write `WORKSPACE/_machine_exec.py` → `run_bash("python3 _machine_exec.py")` |
| `web_fetch` | `url, max_chars=15000` | `httpx` + `BeautifulSoup` strip script/style → text[:max] |
| `web_search` | `query, top_k=5` | `hive.papers.openalex.search(query, top_k)` → title/year/doi/cites/abstract |

`TOOL_SCHEMAS` + `DISPATCH` dict enable `dispatch_tool(name, **kwargs)` `hive/machine/tools.py:90`.

### 6b.3 Agent `hive/machine/agent.py:14`

**SYSTEM** `hive/machine/agent.py:14` describes tools and forces one ` ```json {"tool": "...", "args": {...}} ``` ` per turn, else final markdown answer.

```
User: task
→ [system + user task]
→ loop max_steps 12:
   chat(cfg, messages) → text
   _extract_tool(text) via ```json``` regex → if None → final answer → save_run()
   else dispatch_tool(tool, args) → clipped 8k → messages += assistant text + "[tool result]\n..."
→ if max_steps reached → final summarize prompt → chat → save_run
→ persist via save_run() to HISTORY_DB
```

Providers via `hive.llm.get_provider(cfg)` — same auto Ollama/LM Studio + 404 fallback as research. `run_task(task, cfg, max_steps, verbose)` returns final markdown.

Helpers: `list_history(limit=20)` reads `runs`.

### 6b.4 CLI (`hive/cli.py:220` `machine_app`)

```bash
hive machine              # no args → TUI via machine_callback (invoke_without_command)
hive machine tui          # same, explicit
hive machine run "fetch https://example.com and save summary to report.md" --steps 12
hive machine ls [path] [--recursive]
hive machine read <path>  # relative to workspace
hive machine write <path> "<content>"
hive machine exec --cmd "ls -la"
hive machine python --code "print(2+2)"
hive machine fetch https://example.com
hive machine search "sparse autoencoders" --top 5
hive machine history --limit 20
hive-machine              # entry point hive.machine.app:run (TUI) via pyproject.toml:30
```

All file paths are **relative to workspace** `~/.hive/machine/workspace` and jailed.

### 6b.5 TUI `hive/machine/app.py:22`

`HiveMachineApp` CSS `hive/machine/app.py:40`: `Screen` vertical, `#left 30` / `#center 1fr` / `#right 40` borders `$primary/$secondary/$accent`.

```
┌─ Header (Hive-Machine — local Perplexity Computer, clock) ─┐
├─ Left (30)   │ Center (1fr)           │ Right (40)        │
│ Workspace    │ HELP + RichLog output  │ Preview           │
│ file list    │ (agent chat, tool     │ (first file or    │
│ [Refresh]    │  results, final md)    │  selected file)   │
├─ Task input [fetch…] + steps [12] + Run ───────────────────┤
├─ Footer (q/f/r/h/?) ───────────────────────────────────────┤
```

- `compose()` `hive/machine/app.py:52`: `Header`, `Horizontal#main` with `Vertical#left` (`Static filelist` + `Button Refresh`), `Vertical#center` (`Static HELP` + `RichLog#output`), `Vertical#right` (`RichLog#preview`), `Horizontal#input-row` (`Input#task`, `Input#steps`, `Button#run`).
- `on_mount` focuses task, calls `_refresh_files()` (`list_files(".", false)` → `#filelist` Static, preview first file via `read_file` → `#preview`) and `_refresh_status()` (LLM health `hive/llm/get_provider` → `HELP` footer).
- `on_run/on_submit` → `_dispatch()` `hive/machine/app.py:105`: validates task, parses steps, logs `▶ task`, calls `_run_task(task, steps)` `@work(thread=True)` `hive/machine/app.py:122` → `run_task()` + `call_from_thread(output.write)` + `_refresh_files`.
- `action_show_history` `hive/machine/app.py:135` → `list_history(20)` → bullet list with `datetime`.
- `HELP` `hive/machine/app.py:22`: explains task input, tools, jailed workspace, keys `q/f/r/h/?`.

Tested via `run_test` pilot: `menu count 15` for Research TUI and `filelist`/`task`/`steps` for Machine TUI both render.

### 6b.6 Examples

```bash
# 1. Simple file + code
hive machine run "write hello.py that prints 42 and run it, save output to out.txt" --steps 6
hive machine ls
hive machine read out.txt

# 2. Web + summarize (local LLM)
hive machine run "fetch https://example.com, summarize to report.md with headings, list files" --steps 10

# 3. TUI workflow: hive machine → type "analyze README.md and create summary.md" → Run → preview shows summary.md
```

History persists: `hive machine history` or TUI `h` shows `id, task, steps, datetime` from `machine.db`.

## 7. Paper System

### 7.1 Sources

| Module | Endpoint | Notes |
|---|---|---|
| `hive/papers/openalex.py:1` | `https://api.openalex.org/works?search=&per-page=&sort=relevance_score:desc` | Inverted abstract → text, `primary_location.pdf_url`, `open_access.oa_url`, headers include `User-Agent`. Optional `mailto` for polite pool. |
| `hive/papers/arxiv.py:7` | `https://export.arxiv.org/api/query?search_query=all:…` | `feedparser`, `all:` query, `id_list` fallback. Note: `https` (not `http`) to avoid 301. |
| `hive/papers/crossref.py:1` | `https://api.crossref.org/works/{doi}` | Title, authors, published year, `is-referenced-by-count`. |
| `hive/papers/europe_pmc.py:1` | `https://www.ebi.ac.uk/europepmc/webservices/rest/search` + `/fullTextXML` | OA check `isOpenAccess=Y`, `pmcid`, `BeautifulSoup` XML `sec → title+p` extraction, fallback `body` text. Truncated to 30k. |

`hive/papers/schemas.py:1` defines `Paper`.

### 7.2 Resolver (`hive/papers/resolver.py:1`)

```python
is_doi: r"10\.\d+/.+"
is_arxiv: r"(\d{4}\.\d{4,5}|[a-z\-]+/\d+)" or "arxiv"
resolve(query):
  DOI → openalex.fetch_by_doi else crossref
  arXiv → arxiv.fetch(extract \d{4}\.\d{4})
  OpenAlex ID → openalex.fetch_by_id
  else → openalex.search(query, 1) first hit
fetch_full_text(p): DOI → europe_pmc → oa_url HTML (BS4) → None
```

### 7.3 Ranking details — see §2.4

`hive/papers/rank.py:1` pure deterministic, testable (`tests/test_rank.py:1`).

---

## 8. Research Workflows

Templates in `hive/research/prompts.py:1`, executed by `hive/research/workflows.py:1`.

| Workflow | Prompt | Output |
|---|---|---|
| `deepresearch` | `DEEP_RESEARCH` + `papers_block` + `fulltext_block` (top N sections) | exec summary, background, key findings w/ citations, methods/repro, gaps, checklist rubric 0–3, reading list, limitations |
| `lit` | `LIT_REVIEW` | intro, thematic clusters, methods matrix, results, gaps, refs (lab/PI trajectory if in topic) |
| `compare` | `COMPARE` | matrix rows=papers cols=problem/method/dataset/metrics/results/limitations/repro |
| `review` | `REVIEW` (artifact) | summary, major (critical/major), minor, revision checklist, 0–10 score |
| `audit` | `AUDIT` (paper + notes) | mismatches, missing ablations, irreproducible params, data-leak risks |
| `replicate` | `REPLICATE` | feasibility 0–10, compute/data, step plan, risk table, verification checklist |
| `recipe` | `RECIPE` | ranked recipes: dataset/method/code/hyperparams/verification/compute |
| `draft` | `DRAFT` (prior synthesis) | Title, Abstract, Intro, Related Work, Methods, Experiments, Results, Discussion, Limitations, References |
| `autoresearch` | `AUTORESEARCH` | hypothesis, experiment, expected metric, falsification, code skeleton |
| `watch` | `WATCH` | snapshot, watch queries, baseline metrics (citation velocity, preprints/month) |

Helpers:

```python
def search_and_rank(query, top_k, cfg): openalex.search fallback arxiv → rank
def enrich_full_text(papers, top_n): [(Paper, text|None) for top_n]
def _papers_block(papers): numbered lines with title/authors/year/score/cites/venue/DOI/arXiv/url + abstract[:500]
def _fulltext_block(items): "--- title (doi) ---\n text[:6000]" joined
def run_workflow(kind, topic, cfg, top_k, full_text_top): builds prompt, chat(cfg, [SYSTEM, user]), save_artifact
```

All workflows save to `hive/research/session.py:1` (`new_session(kind:topic)` → `save_artifact(session_id, kind, title, content)`).

---

## 9. Open WebUI Integration

Target: `harishgovardhandamodar/open-webui` (fork of `open-webui/open-webui`).

Two artifacts in `openwebui/` (added via Admin panel or mounted):

### 9.1 Tools (`openwebui/hive_tools.py:1`) — recommended

Each `Tools` method becomes a function-calling tool (OpenAI-compatible tool specs derived from docstrings).

| Tool | Underlying |
|---|---|
| `paper_search(query, top_k=10)` | `search_and_rank` |
| `paper_resolve(identifier, fetch_full_text=False)` | `resolver.resolve` + `fetch_full_text` |
| `paper_rank_with_evidence(query, top_k, full_text_top)` | rank + `RANK_RESCORING` via local LLM |
| `deepresearch(topic, top_k)` | `run_workflow("deepresearch")` |
| `literature_review(topic, top_k)` | `lit` |
| `compare_papers(topic, top_k)` | `compare` |
| `review_artifact(artifact)` | `review` |
| `audit_paper_vs_code(item)` | `audit` |
| `replication_plan(paper)` | `replicate` |
| `ml_recipe(task)` | `recipe` |
| `draft_paper(topic)` | `draft` |
| `autoresearch(idea)` | `autoresearch` |

`Valves` (`hive_tools.py:17`):

```python
provider="auto", ollama_url="http://localhost:11434", ollama_model="llama3.1:8b",
lmstudio_url="http://localhost:1234/v1", lmstudio_model="qwen/qwen3.8-27b",
default_top_k=10, full_text_top=3
```

**Install:**

1. On Open WebUI host (same venv or container): `pip install -e /path/to/hive-research-CLI`.
2. Open WebUI → Admin Panel → Tools → **+ Create Tool** → paste `openwebui/hive_tools.py` (entire file).
3. In Valves (tool settings), set `ollama_url`:
   - Bare metal: `http://localhost:11434`
   - Docker (`ghcr.io/open-webui/open-webui:main`): `http://host.docker.internal:11434` **and** run container with `--add-host=host.docker.internal:host-gateway`.
   - Similarly `lmstudio_url` → `http://host.docker.internal:1234/v1` if LM Studio on host.
4. Chat → enable **Tools** toggle → ask “Rank papers on sparse autoencoders” → model calls `paper_search`.

**Direct fork integration:**

```bash
cp openwebui/hive_tools.py ../open-webui/backend/open_webui/tools/hive_research.py
# add to backend/requirements.txt if not via pip -e
```

### 9.2 Pipe (`openwebui/hive_pipe.py:1`) — fallback for models without tool support

- `Pipe` with `Valves(enabled, inject_papers, top_k=5, trigger_keywords="paper,research,review,literature,arxiv,doi")` `hive_pipe.py:13`.
- `pipes()` → `[{"id": "hive-research", "name": "Hive Research (local papers)"}]`.
- `pipe(body)` checks last user message for triggers (`paper`, `research`, …), calls `search_and_rank(last[:300], top_k)` and injects system context: `"[Hive Research — local paper context…] - title (year) doi score cites — abstract[:200]"` before last message, so even tiny local models answer grounded.

Install: Admin → Pipes → **+ Create Pipe** → paste `hive_pipe.py` → select model `Hive Research (local papers)`.

### 9.3 Verification (without Open WebUI)

```bash
python -c "import openwebui.hive_tools; print([m for m in dir(openwebui.hive_tools.Tools) if not m.startswith('_')])"
python -c "import openwebui.hive_pipe; print('pipe ok')"
hive doctor; hive rank "diffusion" --top 5 --no-llm  # deterministic
hive rank "diffusion" --full-text-top 2             # with local LLM
```

See `openwebui/README.md:1` for full Valves table and Docker notes.

---

## 10. Data & Provenance

- **No external DB.** `~/.hive/hive.db` SQLite (`hive/research/session.py:1`) stores every synthesis (`artifacts.kind` = workflow name). Query via `hive sessions` or `sqlite3 ~/.hive/hive.db "select * from artifacts;"`.
- **Exports** `~/.hive/exports/` served by `hive serve` (`hive/cli.py:224`, `HTTPServer` + `SimpleHTTPRequestHandler`).
- **Provenance:** every paper lists `cited_by_count`, `venue`, `is_open_access`, `oa_url/pdf_url`, `publication_date`; syntheses cite `[Author Year]` or DOI links and include `score_breakdown` and, when LLM rescored, `new_score` JSON per paper.
- **Privacy:** no telemetry; LLM calls stay on `localhost`.

---

## 11. Development

### 11.1 Layout

```
.
├── hive/               # see §2.1
├── openwebui/          # Tools + Pipe
├── tests/              # test_cli.py, test_config.py, test_llm.py, test_rank.py
├── pyproject.toml      # hatchling, scripts, dependencies
├── README.md           # quickstart (points here)
├── DOCUMENTATION.md    # this file
├── .env.example        # provider URLs + OPENALEX_MAILTO
└── .gitignore          # __pycache__, .venv, dist, .hive, exports
```

### 11.2 Setup & tests

```bash
python -m venv .venv; source .venv/bin/activate
pip install -e ".[dev]"
pytest -q                # 8 tests — config, rank, llm mocks, cli --help/doctor/version
pytest tests/test_rank.py -v
python -m hive.cli --help
python -c "from hive.tui.app import HiveTUI; HiveTUI()"  # import check

# TUI pilot test (async)
python - << 'PY'
import asyncio
from hive.tui.app import HiveTUI
async def main():
    app = HiveTUI()
    async with app.run_test() as pilot:
        await pilot.pause()
        print(len(list(app.query_one("#menu-list").children)))
asyncio.run(main())
PY
```

Mocks `tests/test_llm.py:1` patch `httpx.Client` for Ollama/LM Studio.

### 11.3 Adding a workflow

1. Add prompt template to `hive/research/prompts.py:1` (e.g. `MYFLOW = """... {topic} {papers_block} ..."""`).
2. Add to `mapping` in `hive/research/workflows.py:20` (`"myflow": prompts.MYFLOW`).
3. Add CLI command in `hive/cli.py:1` (`@app.command("myflow") def myflow(...): _workflow_cmd("myflow", ...)`).
4. Add TUI menu entry `hive/tui/app.py:23` (`("myflow", "My Flow")`) and handle in `_dispatch`/`_run_workflow`.
5. Add Tool method in `openwebui/hive_tools.py:1` (docstring → tool spec).
6. Test: `hive myflow "test" --top 5` and `hive tui` → menu.

### 11.4 Release

```bash
# bump hive/__init__.py:__version__ and pyproject.toml:version
pip install build; python -m build
twine upload dist/*
```

---

## 12. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `hive doctor` → `Ollama … 404` / `No local LLM` | `ollama_model` mismatch (`llama3.1` vs `llama3.1:8b`) | `hive config --ollama-model llama3.1:8b` or rely on fallback (auto lists models). `hive models` shows exact names. |
| `LM Studio … 404` / `local-model` | LM Studio default `local-model` not real id | `hive config --lmstudio-model qwen/qwen3.8-27b` (use id from `http://localhost:1234/v1/models`). |
| `arXiv: 301` | `http://export.arxiv.org` redirect | Fixed in `hive/papers/arxiv.py:7` → `https`; `hive doctor` now checks `https`. |
| `Client error 404 for url .../api/chat` | Model not found (old Ollama) | Fallback in `hive/llm/client.py:30` retries with first available model; update `~/.hive/config.toml`. |
| `No papers found` | Query too narrow / OpenAlex rate-limit | Try broader query, `--top` 5, check `curl "https://api.openalex.org/works?search=test&per-page=1"`; set `OPENALEX_MAILTO` in `.env` for polite pool. |
| `MountError: Can't mount ... ListView` | TUI `append` pre-mount (old code) | Fixed `hive/tui/app.py:86` → `ListView(*items)`. |
| `Textual not installed` on `hive tui` | missing optional dep | `pip install textual` or `pip install -e ".[tui]"`. |
| Open WebUI Tools not called | Docker networking | Use `http://host.docker.internal:11434` + `--add-host=host.docker.internal:host-gateway`; set Valves accordingly; enable Tools toggle in chat. |
| `No legal full-text` | Paper not OA / no pmcid | Expected for closed-access; try `doi` with OA flag or arXiv version. |

`hive --help` and `hive tui --help` always available; `hive config --show` dumps resolved config (file + env).

---

## 13. Roadmap & Limitations

**Done:** CLI parity for `rank/paper/ask` + 9 workflows, TUI workbench (Textual) with threaded workers and menu, LLM auto-detect + 404 fallback, OpenAlex/arXiv/Crossref/Europe PMC, deterministic rank, SQLite sessions, Open WebUI Tools + Pipe, docs, tests.

**Intentionally omitted vs. full Feynman:**
- Pi agent runtime, Modal/RunPod compute, PostHog, full `~/.feynman/orgs/.../workbench` ledger — replaced by minimal `hive serve` + `~/.hive/hive.db`.
- AlphaXiv annotations, Hugging Face `ml-intern` recipes, 100+ BioTools (only core paper APIs implemented; `hive/papers/` is extensible).
- Ketcher chemistry, Jupyter/LaTeX previews — out of scope for local CLI.

**Next:** watch scheduler (`cron` + `hive watch`), embedding/RAG via `nomic-embed-text` (already in Ollama), PDF full-text via `pypdf`/`pdfminer`, `hive export` to markdown/LaTeX, Textual `DataTable` for rank results.

---

## 14. License

MIT. Feynman is © companion-inc/feynman. This is an independent local-only implementation. See `README.md:132`.

---

*Generated for `hive-research 0.1.0` — run `hive doctor` and `hive tui` to verify.*
