"""
Hive Research — Open WebUI Pipe (optional)
===========================================
A Pipe intercepts the chat stream and can inject paper context before the model
answers. Install as a Pipe in Open WebUI (Admin → Pipes).

Use case: user asks a research question, the pipe auto-searches papers and
prepends them as context, so even a small local model can answer grounded.

This is optional — the Tools file above is preferred for function-calling
models. Use this pipe for models without tool support.
"""

from __future__ import annotations

from typing import AsyncGenerator, Callable, Awaitable
from pydantic import BaseModel, Field

try:
    from hive.config import load_config
    from hive.research.workflows import search_and_rank

    _HAS_HIVE = True
except ImportError:
    _HAS_HIVE = False


class Pipe:
    class Valves(BaseModel):
        enabled: bool = Field(default=True)
        inject_papers: bool = Field(default=True, description="Inject paper context for research-like prompts")
        top_k: int = Field(default=5)
        trigger_keywords: str = Field(default="paper,research,review,literature,arxiv,doi", description="Comma-separated triggers")

    def __init__(self):
        self.valves = self.Valves()
        self.type = "pipe"

    def pipes(self):
        return [{"id": "hive-research", "name": "Hive Research (local papers)"}]

    async def pipe(
        self, body: dict, __user__: dict | None = None, __event_emitter__: Callable | None = None
    ) -> AsyncGenerator[str, None] | str | dict:
        if not _HAS_HIVE or not self.valves.enabled:
            return body

        messages = body.get("messages", [])
        if not messages:
            return body

        last = messages[-1].get("content", "") if isinstance(messages[-1].get("content"), str) else str(messages[-1].get("content"))
        triggers = [t.strip().lower() for t in self.valves.trigger_keywords.split(",")]
        should_inject = self.valves.inject_papers and any(kw in last.lower() for kw in triggers)

        if should_inject and len(last.split()) > 3:
            try:
                cfg = load_config()
                papers = search_and_rank(last[:300], top_k=self.valves.top_k, cfg=cfg)
                if papers:
                    ctx = "\n".join(
                        f"- {p.title} ({p.year or 'n.d.'}) {p.doi or p.arxiv_id or ''} score={p.score} cites={p.cited_by_count} — {(p.abstract or '')[:200]}"
                        for p in papers
                    )
                    system_ctx = {
                        "role": "system",
                        "content": f"[Hive Research — local paper context for: {last[:120]}]\n{ctx}\nGround your answer in these papers and cite them. If unsure, say so.",
                    }
                    # insert before last user message
                    messages.insert(-1, system_ctx)
                    body["messages"] = messages
            except Exception:
                pass

        return body
