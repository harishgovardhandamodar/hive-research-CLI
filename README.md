<p align="center"><strong>Hive Research</strong><br/>Local-only Feynman clone — Ollama & LM Studio only — CLI + TUI + Open WebUI</p>

Feynman feature-by-feature, no cloud LLM. Papers via OpenAlex / arXiv / CrossRef / Europe PMC. Synthesis via your local model. CLI + TUI workbench + Open WebUI Tools/Pipe.

> **Full docs:** [`DOCUMENTATION.md`](DOCUMENTATION.md) — architecture, config, CLI/TUI reference, Open WebUI guide, troubleshooting.

## Install

```bash
git clone https://github.com/harishgovardhandamodar/hive-research-CLI
cd hive-research-CLI
pip install -e .

# or
uv pip install -e .
```

Prereqs: one local LLM running

- **Ollama**: `ollama serve && ollama pull llama3.1` (or `qwen2.5:7b`, `mistral`, …)
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
| `feynman serve` | `hive serve` (minimal artifact preview) + `hive tui` (full TUI workbench) |
| `/deepresearch <topic>` | `hive deepresearch <topic>` or `/deepresearch <topic>` in REPL/TUI |
| `/lit` | `hive lit <topic>` |
| `/review` | `hive review <artifact>` |
| `/audit` | `hive audit <item>` |
| `/replicate` | `hive replicate <paper>` |
| `/recipe` | `hive recipe <task>` |
| `/compare` | `hive compare <topic>` |
| `/draft` | `hive draft <topic>` |
| `/autoresearch` | `hive autoresearch <idea>` |
| `/watch` | `hive watch <topic>` |
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
hive ask "explain PaperRank scoring transparently"

# TUI — full workbench (like Feynman Pi terminal)
hive tui
#  → left menu: Rank | Paper | Ask | DeepResearch | Lit | Compare … | Sessions | Doctor
#  → Enter topic → view ranked papers + LLM rescoring, streamed
#  → `q` quit, `f` focus, `s` sessions, `d` doctor, `?` help

# Interactive REPL (lightweight alternative to TUI)
hive
hive> /deepresearch mechanistic interpretability
hive> rank sparse autoencoders
hive> paper 10.1038/s41586-023-00000-0 --fetch-full-text
```

`--no-llm` gives deterministic ranking without calling the local model (useful offline).

## Local LLM routing

```
hive.config.provider = auto  # try Ollama health, then LM Studio, else error
                     = ollama   # force Ollama  (http://localhost:11434/api/chat)
                     = lmstudio # force LM Studio (http://localhost:1234/v1/chat/completions)
```

Both providers implement the same `chat`/`chat_stream` interface; swap freely. Streaming works.

## Open WebUI integration

Target fork: `harishgovardhandamodar/open-webui`.

Two artifacts in `openwebui/`:

- `hive_tools.py` — **Tools** (function calling). Each method = one tool (paper_search, deepresearch, lit, etc.). Preferred for tool-calling local models (Ollama with `tools` support, LM Studio Qwen/Mistral).
- `hive_pipe.py` — **Pipe** fallback for models without tools; auto-injects ranked papers as context.

**Setup** (see `openwebui/README.md`):

1. `pip install -e .` on the Open WebUI host.
2. Admin → Tools → + paste `hive_tools.py` → set Valves (`ollama_url` → `http://host.docker.internal:11434` if Docker).
3. Enable Tools in chat.

Docker tip: run Open WebUI with `--add-host=host.docker.internal:host-gateway`.

## Data & provenance

- Paper search: OpenAlex + arXiv (public, no keys). DOI via CrossRef. Full-text via Europe PMC OA + OA URL.
- Local DB: `~/.hive/hive.db` (sessions, artifacts). Exports: `~/.hive/exports`.
- All claims are source-grounded: every synthesis cites `title · venue · DOI/URL`.

## Project layout

```
hive/
  config.py        # ~/.hive/config.toml + env
  llm/             # ollama.py, lmstudio.py, base.py, client.py (auto-detect)
  papers/          # openalex.py, arxiv.py, crossref.py, europe_pmc.py, rank.py, resolver.py
  research/        # prompts.py, workflows.py, session.py
  tui/             # app.py — Textual workbench (Hive-Research TUI)
  cli.py           # Typer app (hive / hive-research) + `hive tui` + REPL
openwebui/
  hive_tools.py    # Open WebUI Tools spec
  hive_pipe.py     # Open WebUI Pipe spec
```

## Tests

```bash
pip install -e ".[dev]"
pytest -q
```

## License

MIT — Feynman is © companion-inc/feynman.
