"""
Hive Research — Open WebUI Tools
=================================
Drop this file into Open WebUI's Tools UI (Admin → Tools → +) or mount via
`data/tools/`. Each public method becomes a function-calling tool for any
local model that supports tools (Ollama tool-calling, LM Studio, etc.).

Requires: `hive-research` installed on the Open WebUI server host (same venv
or `pip install -e /path/to/hive-research-CLI`). No cloud keys.

All LLM work inside the tool uses the host's local LLM via Ollama/LMStudio,
so the tool itself can be called with a tiny local model as orchestrator.

Docs: https://github.com/harishgovardhandamodar/hive-research-CLI#open-webui
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field

try:
    from hive.config import load_config
    from hive.papers import openalex, arxiv
    from hive.papers import rank as rank_mod, resolver as resolver_mod
    from hive.research.workflows import search_and_rank, run_workflow

    _HAS_HIVE = True
except ImportError:
    _HAS_HIVE = False


class Tools:
    class Valves(BaseModel):
        provider: str = Field(default="auto", description="ollama | lmstudio | auto")
        ollama_url: str = Field(default="http://localhost:11434")
        ollama_model: str = Field(default="llama3.1", description="Model for research synthesis (local)")
        lmstudio_url: str = Field(default="http://localhost:1234/v1")
        lmstudio_model: str = Field(default="local-model")
        default_top_k: int = Field(default=10, description="Default paper count")
        full_text_top: int = Field(default=3, description="Full-text fetch count for rescoring")

    def __init__(self):
        self.valves = self.Valves()
        self._cfg = None

    def _cfg_obj(self):
        if not _HAS_HIVE:
            raise RuntimeError("hive-research not installed on server. pip install hive-research")
        from hive.config import AppConfig, LLMConfig

        cfg = load_config()
        # valves override
        cfg.llm.provider = self.valves.provider  # type: ignore
        cfg.llm.ollama_url = self.valves.ollama_url
        cfg.llm.ollama_model = self.valves.ollama_model
        cfg.llm.lmstudio_url = self.valves.lmstudio_url
        cfg.llm.lmstudio_model = self.valves.lmstudio_model
        cfg.default_top_k = self.valves.default_top_k
        cfg.full_text_top = self.valves.full_text_top
        return cfg

    # ── paper tools ──────────────────────────────────────────────

    def paper_search(
        self, query: str, top_k: int = 10
    ) -> str:
        """
        Search papers via OpenAlex (and arXiv fallback) and return ranked list with scores.
        Use for: "find papers on X", "what should I read about Y", PaperRank.

        :param query: topic query, e.g. "sparse autoencoders mechanistic interpretability"
        :param top_k: how many papers (1-20)
        """
        cfg = self._cfg_obj()
        papers = search_and_rank(query, top_k=top_k, cfg=cfg)
        if not papers:
            return "No papers found."
        lines = []
        for i, p in enumerate(papers, 1):
            lines.append(
                f"{i}. **{p.title}** — {', '.join(p.authors[:3])} ({p.year or 'n.d.'}) "
                f"[score {p.score} | cites {p.cited_by_count} | {p.venue or ''}] "
                f"DOI:{p.doi or '-'} arXiv:{p.arxiv_id or '-'} URL:{p.url or p.oa_url or ''} "
                f"breakdown={p.score_breakdown}"
            )
        return "\n".join(lines)

    def paper_resolve(
        self, identifier: str, fetch_full_text: bool = False
    ) -> str:
        """
        Resolve one paper by DOI, arXiv ID, OpenAlex ID, or title. Optionally fetch legal full-text sections (Europe PMC / OA).

        :param identifier: e.g. "10.7717/peerj.4375" or "2301.12345" or "Attention is all you need"
        :param fetch_full_text: if true, try Europe PMC / OA full-text fetch
        """
        p = resolver_mod.resolve(identifier)
        if not p:
            return f"Could not resolve: {identifier}"
        header = (
            f"# {p.title}\nAuthors: {', '.join(p.authors)}\nVenue: {p.venue} {p.year or ''}\n"
            f"DOI: {p.doi}\nURL: {p.url or p.oa_url or p.pdf_url}\nCited by: {p.cited_by_count} OA:{p.is_open_access}\n\n{p.abstract or ''}"
        )
        if fetch_full_text:
            txt = resolver_mod.fetch_full_text(p)
            if txt:
                return header + f"\n\n## Full-text evidence (truncated)\n{txt[:8000]}"
            return header + "\n\n(no legal full-text available)"
        return header

    def paper_rank_with_evidence(
        self, query: str, top_k: int = 10, full_text_top: int = 3
    ) -> str:
        """
        PaperRank with section-aware full-text evidence and LLM rescoring.
        Mirrors `feynman rank <topic> --full-text-top 3`.

        :param query: topic
        :param top_k: papers to rank
        :param full_text_top: how many top papers to fetch full-text for rescoring
        """
        cfg = self._cfg_obj()
        papers = search_and_rank(query, top_k=top_k, cfg=cfg)
        if not papers:
            return "No papers found."
        from hive.research.workflows import enrich_full_text
        from hive.llm import ChatMessage, chat
        from hive.research.prompts import RANK_RESCORING

        ft = enrich_full_text(papers, top_n=full_text_top)
        block = "\n".join(f"{p.id}: {p.title} score={p.score} {p.score_breakdown}" for p in papers)
        ft_block = "\n".join(f"{p.title}\n{(txt or '')[:4000]}" for p, txt in ft)
        prompt = RANK_RESCORING.format(topic=query, papers_block=block, fulltext_block=ft_block)
        resp = chat(cfg, [ChatMessage(role="system", content="You are a ranking assistant. Return JSON and brief justification."), ChatMessage(role="user", content=prompt)])
        ranked = "\n".join(f"{i}. {p.title} [score {p.score} {p.score_breakdown}]" for i, p in enumerate(papers, 1))
        return f"## Deterministic ranking\n{ranked}\n\n## LLM rescoring (full-text top {full_text_top})\n{resp.content}"

    # ── research workflows ───────────────────────────────────────

    def deepresearch(self, topic: str, top_k: int = 10) -> str:
        """
        Source-heavy multi-agent investigation (like /deepresearch). Synthesizes papers + full-text into a report with citations, gaps, and reading list.

        :param topic: research topic
        :param top_k: papers to ground on
        """
        cfg = self._cfg_obj()
        return run_workflow("deepresearch", topic, cfg, top_k=top_k, full_text_top=cfg.full_text_top)

    def literature_review(self, topic: str, top_k: int = 12) -> str:
        """
        Literature review from paper search and primary sources (like /lit).

        :param topic: topic or lab/PI
        :param top_k: papers
        """
        cfg = self._cfg_obj()
        return run_workflow("lit", topic, cfg, top_k=top_k, full_text_top=cfg.full_text_top)

    def compare_papers(self, topic: str, top_k: int = 10) -> str:
        """
        Source comparison matrix (like /compare).

        :param topic: topic
        :param top_k: papers
        """
        cfg = self._cfg_obj()
        return run_workflow("compare", topic, cfg, top_k=top_k, full_text_top=cfg.full_text_top)

    def review_artifact(self, artifact: str) -> str:
        """Research review with severity and revision plan (like /review). :param artifact: artifact description or pasted text"""
        cfg = self._cfg_obj()
        return run_workflow("review", artifact, cfg)

    def audit_paper_vs_code(self, item: str) -> str:
        """Paper vs codebase mismatch audit (like /audit). :param item: paper + codebase notes"""
        cfg = self._cfg_obj()
        return run_workflow("audit", item, cfg)

    def replication_plan(self, paper: str) -> str:
        """Plan replication checks (like /replicate). :param paper: DOI/title"""
        cfg = self._cfg_obj()
        return run_workflow("replicate", paper, cfg)

    def ml_recipe(self, task: str) -> str:
        """Ranked ML training recipes (like /recipe). :param task: task or paper"""
        cfg = self._cfg_obj()
        return run_workflow("recipe", task, cfg)

    def draft_paper(self, topic: str) -> str:
        """Paper-style draft from research findings (like /draft). :param topic: topic"""
        cfg = self._cfg_obj()
        return run_workflow("draft", topic, cfg)

    def autoresearch(self, idea: str) -> str:
        """Bounded experiment loop (like /autoresearch). :param idea: idea"""
        cfg = self._cfg_obj()
        return run_workflow("autoresearch", idea, cfg)
