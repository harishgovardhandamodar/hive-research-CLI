<p align="center"><strong>Hive Research + Hive-Machine</strong><br/>Local-only Feynman clone + Perplexity Computer — Ollama & LM Studio only — CLI + TUI + Machine + Open WebUI</p>

Feynman feature-by-feature, no cloud LLM. Papers via OpenAlex / arXiv / CrossRef / Europe PMC. Synthesis via your local model. Adds **Hive-Machine** — sandboxed Perplexity Computer (files, code, web, terminal) on `~/.hive/machine/workspace`.

> **Full docs:** [`DOCUMENTATION.md`](DOCUMENTATION.md) — architecture, config, CLI/TUI/Machine reference, Open WebUI guide, troubleshooting. **Hive-Machine deep dive:** [`docs/HIVE_MACHINE.md`](docs/HIVE_MACHINE.md) (mermaid architecture, workflows, audit, dashboards).

## Install

```bash
git clone https://github.com/harishgovardhandamodar/hive-research-CLI
cd hive-research-CLI
pip install -e .                 # CLI + TUI + Machine (textual included)
# or: pip install -e ".[tui]"
# or: uv pip install -e .
```

Prereqs: one local LLM running

- **Ollama**: `ollama serve && ollama pull llama3.1:8b` (or `qwen3.8:27b-mlx`, `mistral`, `deepseek-r1:32b` …)
- **LM Studio**: open LM Studio → Local Server → Start Server (default `http://localhost:1234/v1`)

```bash
hive doctor          # check both
hive models          # list local models
hive config --show   # view config
```

Config: `~/.hive/config.toml` or env (`HIVE_PROVIDER`, `OLLAMA_BASE_URL`, `LMSTUDIO_BASE_URL`, etc.). See `.env.example`.

## CLI — mirrors Feynman

| Feynman | Hive equivalent |
|---------|-----------------|
| `feynman rank <topic> --full-text-top 3` | `hive rank <topic> --full-text-top 3` |
| `feynman paper <id> --fetch-full-text` | `hive paper <id> --fetch-full-text` |
| `feynman serve` | `hive serve` (minimal HTTP) + `hive tui` (Research workbench) |
| `/deepresearch <topic>` | `hive deepresearch <topic>` or `/deepresearch` in REPL/TUI |
| `/lit` | `hive lit <topic>` |
| `/review` | `hive review <artifact>` |
| `/audit` | `hive audit <item>` |
| `/replicate` | `hive replicate <paper>` |
| `/recipe` | `hive recipe <task>` |
| `/compare` | `hive compare <topic>` |
| `/draft` | `hive draft <topic>` |
| `/autoresearch` | `hive autoresearch <idea>` |
| `/watch` | `hive watch <topic>` |
| *(new)* Deep Report | `hive report <topic> --top 12 --depth deep` — 20-section Feynman parity (hero, provenance, Pi chat, BioTools, synthesis, matrix, evidence, previews, checklist, compute/lineage, audit, gaps, reading list, changelog) |
| `/thinking` | `hive config --provider … --ollama-model …` |
| `/outputs` | `hive sessions` |

### Examples

```bash
hive rank "mechanistic interpretability sparse autoencoders" --top 10
hive rank "diffusion models" --full-text-top 3 --json > ranked.json
hive paper 10.7717/peerj.4375 --fetch-full-text
hive paper 2301.12345
hive deepresearch "test-time scaling for LLM reasoning" --top 12
hive lit "NeurIPS 2024 best papers on retrieval"
hive compare "RLHF vs DPO" --top 8
hive draft "survey on synthetic data for code"
hive report "AI Agents" --top 12 --depth deep  # 20-section deep analysis (Feynman TUI parity)
hive ask "explain PaperRank scoring transparently"

# TUI — Research workbench (like Feynman Pi terminal)
hive tui
#  → left: Rank | Paper | Ask | DeepResearch | Lit | Compare … | Sessions | Doctor
#  → Enter topic → ranked papers + LLM rescoring
#  → `q` quit, `f` focus, `s` sessions, `d` doctor, `?` help

# REPL (lightweight alternative)
hive
hive> /deepresearch mechanistic interpretability
hive> rank sparse autoencoders
```

`--no-llm` gives deterministic ranking without calling local model (offline).

## Hive-Machine — Perplexity Computer (local)

Sandboxed computer at `~/.hive/machine/workspace` (jailed, no escape). Local LLM loops via 8 tools: `list_files`, `read_file`, `write_file`, `delete_path`, `run_bash`, `run_python`, `web_fetch`, `web_search`.

```bash
# TUI (recommended) — file tree left, agent chat center, preview right
hive machine              # no args → TUI
hive machine tui
hive-machine              # alias
#  → task input bottom: "fetch https://example.com and save summary to report.md + run python to plot"
#  → agent loops max_steps (default 12) via Ollama/LM Studio, writes files, shows preview
#  → `q` quit, `r` refresh files, `h` history, `f` focus, `?` help

# Headless (CI / scripts)
hive machine run "list files and summarize README.md to summary.md" --steps 12
hive machine run "fetch https://arxiv.org/abs/2301.12345 and extract method section" --steps 8

# Direct workspace ops (no LLM)
hive machine ls
hive machine ls --recursive
hive machine read report.md
hive machine write hello.txt "hello machine"
hive machine exec --cmd "ls -la && cat hello.txt"
hive machine python --code "print(2+2)"
hive machine fetch https://example.com
hive machine search "sparse autoencoders" --top 5
hive machine history --limit 20
```

Workspace is `~/.hive/machine/workspace` — all file/code ops are jailed there. History DB `~/.hive/machine/machine.db`.

See `DOCUMENTATION.md` § Hive-Machine for agent prompt, tool schemas, and sandbox details.

## Local LLM routing

```
hive.config.provider = auto  # try Ollama health, then LM Studio, else error
                     = ollama   # force Ollama  (http://localhost:11434/api/chat)
                     = lmstudio # force LM Studio (http://localhost:1234/v1/chat/completions)
```

Both providers implement same `chat`/`chat_stream`; swap freely. Streaming works. 404 fallback auto-retries with first available model.

## Open WebUI integration

Target fork: `harishgovardhandamodar/open-webui`.

Two artifacts in `openwebui/`:

- `hive_tools.py` — **Tools** (13 tools: paper_search, deepresearch, lit, etc.). Preferred for tool-calling models.
- `hive_pipe.py` — **Pipe** fallback for non-tool models; auto-injects ranked papers.

**Setup** (see `openwebui/README.md`):
1. `pip install -e .` on Open WebUI host.
2. Admin → Tools → + paste `hive_tools.py` → Valves (`ollama_url` → `http://host.docker.internal:11434` if Docker).
3. Enable Tools in chat.

Docker tip: `docker run --add-host=host.docker.internal:host-gateway ...`

## Data & provenance

- Paper search: OpenAlex + arXiv (public), DOI via Crossref, full-text via Europe PMC OA.
- Local DB: `~/.hive/hive.db` (research), `~/.hive/machine/machine.db` (machine runs). Exports: `~/.hive/exports`.
- All claims source-grounded: `title · venue · DOI/URL` + `score_breakdown` + LLM `new_score` JSON.

## Project layout

```
hive/
  config.py          # ~/.hive/config.toml + env
  llm/               # ollama.py, lmstudio.py, base.py, client.py (auto-detect + 404 fallback)
  papers/            # openalex.py, arxiv.py, crossref.py, europe_pmc.py, rank.py, resolver.py
  research/          # prompts.py, workflows.py, session.py
  tui/               # app.py — Research TUI
  machine/           # Hive-Machine (Perplexity Computer): app.py, tools.py, agent.py
  cli.py             # Typer app (hive / hive-research) + `hive machine` + REPL
openwebui/
  hive_tools.py      # Open WebUI Tools
  hive_pipe.py       # Open WebUI Pipe
```

## Tests

```bash
pip install -e ".[dev]"
pytest -q            # 8 tests
python -c "from hive.tui.app import HiveTUI; from hive.machine.app import HiveMachineApp; print('ok')"
```

## License

MIT — Feynman is © companion-inc/feynman.
