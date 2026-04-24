#!/usr/bin/env python
# -*- coding: utf-8 -*-

from metagpt.actions import Action
from metagpt.actions.paper_research.search_papers import SearchAcademicPapers
from metagpt.logs import logger


class LiteratureReviewAction(Action):
    """Collect concise literature context before software collaboration starts."""

    name: str = "LiteratureReviewAction"
    desc: str = "Collect paper search context for product and architecture planning"

    async def run(self, topic: str, max_results: int = 5, language: str = "en") -> dict:
        logger.info(f"Preparing literature review context for topic: {topic}")
        search_action = SearchAcademicPapers(max_results=max_results)
        search_action.set_context(self.context)
        search_action.set_llm(self.llm)

        summary = await search_action.run(topic=topic, sources=["arxiv"], language=language)
        papers = search_action.get_last_search_papers()
        key_papers = []
        for paper in papers[:max_results]:
            key_papers.append(
                {
                    "title": paper.title,
                    "year": paper.year,
                    "venue": paper.venue or "arXiv",
                    "url": paper.open_access_pdf or paper.url,
                    "abstract": (paper.abstract or "")[:300],
                }
            )

        return {"topic": topic, "summary": summary, "papers": key_papers}
