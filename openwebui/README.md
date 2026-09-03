# Hive Research — Open WebUI Integration

Local-only, no cloud keys.

## Option 1: Tools (recommended, function-calling models)

1. Install `hive-research` on the **Open WebUI host** (same Python env or adjacent):
   ```bash
   pip install -e /path/to/hive-research-CLI
   # or
   pip install hive-research
   ```

2. In Open WebUI: **Admin Panel → Tools → + Create Tool** → paste contents of `hive_tools.py`.

3. In **Valves** (tool settings), set:
   - `provider`: `auto` | `ollama` | `lmstudio`
   - `ollama_url`: `http://host.docker.internal:11434` if Open WebUI runs in Docker
   - `ollama_model` / `lmstudio_model`: your local model id (`llama3.1`, `qwen2.5:7b`, `local-model`, etc.)

4. Enable Tools in a chat (check the Tools toggle), ask: *"Rank papers on sparse autoencoders"* — model will call `paper_search` etc.

### Docker networking

If Open WebUI runs as `ghcr.io/open-webui/open-webui:main`, set:

- Ollama: `--add-host=host.docker.internal:host-gateway` and valve `ollama_url=http://host.docker.internal:11434`
- LM Studio: same, `lmstudio_url=http://host.docker.internal:1234/v1`

## Option 2: Pipe (models without tool support)

1. **Admin Panel → Pipes → + Create Pipe** → paste `hive_pipe.py`.
2. Select model `Hive Research (local papers)` in new chat.
3. Ask research questions containing trigger keywords (`paper`, `research`, etc.) — pipe auto-injects ranked papers as system context.

## Option 3: Direct via fork

If you use `harishgovardhandamodar/open-webui` fork, copy these files into the fork's `backend/`:

```bash
cp openwebui/hive_tools.py  ../open-webui/backend/open_webui/tools/hive_research.py
cp openwebui/hive_pipe.py   ../open-webui/backend/open_webui/pipes/hive_research.py
```

and add to `backend/requirements.txt`: local deps are already in `pyproject.toml`.

## Valves reference

| Valve | Default | Notes |
|-------|---------|-------|
| provider | auto | auto-detect ollama→lmstudio |
| ollama_url | http://localhost:11434 | Docker → host.docker.internal |
| ollama_model | llama3.1 | `ollama list` |
| lmstudio_url | http://localhost:1234/v1 | LM Studio → Local Server |
| lmstudio_model | local-model | shown in LM Studio |
| default_top_k | 10 | papers per search |
| full_text_top | 3 | Europe PMC fetches |

## Testing without Open WebUI

```bash
hive doctor
hive rank "diffusion models" --top 5 --no-llm   # deterministic only
hive rank "diffusion models" --full-text-top 2  # with local LLM
hive paper 10.7717/peerj.4375 --fetch-full-text
```
