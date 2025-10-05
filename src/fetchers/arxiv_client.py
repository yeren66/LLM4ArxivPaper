"""Utilities for fetching papers from arXiv."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import List

import arxiv

from core.config_loader import FetchConfig
from core.models import PaperCandidate, TopicTask


def _build_query(task: TopicTask) -> str:
    parts = []

    if task.query.include_keywords:
        include = " OR ".join(f"all:\"{kw}\"" for kw in task.query.include_keywords)
        parts.append(f"({include})")

    if task.query.categories:
        cats = " OR ".join(f"cat:{cat}" for cat in task.query.categories)
        parts.append(f"({cats})")

    if not parts:
        # 默认回退到最常用的计算机科学分类
        parts.append("(cat:cs.AI OR cat:cs.CL OR cat:cs.SE OR cat:cs.LG)")

    return " AND ".join(parts)


def _sanitize_arxiv_id(entry_id: str) -> str:
    arxiv_id = entry_id.split("/")[-1]
    return arxiv_id.split("v")[0]


def fetch_candidates(task: TopicTask, fetch_cfg: FetchConfig) -> List[PaperCandidate]:
    """Fetch recent papers for the given topic."""

    query = _build_query(task)
    search = arxiv.Search(
        query=query,
        max_results=fetch_cfg.max_papers_per_topic,
        sort_by=arxiv.SortCriterion.SubmittedDate,
        sort_order=arxiv.SortOrder.Descending,
    )

    client = arxiv.Client()

    cutoff = datetime.utcnow() - timedelta(days=fetch_cfg.days_back)
    candidates: List[PaperCandidate] = []

    for result in client.results(search):
        published = result.published.replace(tzinfo=None) if result.published else None
        if published and published < cutoff:
            continue

        text_blob = (result.title + " " + result.summary).lower()
        if any(kw.lower() in text_blob for kw in task.query.exclude_keywords):
            continue

        candidate = PaperCandidate(
            arxiv_id=_sanitize_arxiv_id(result.entry_id),
            title=result.title.strip(),
            abstract=result.summary.strip(),
            authors=[author.name for author in result.authors],
            categories=list(result.categories or []),
            published=published,
            extra={
                "arxiv_url": result.entry_id,
                "pdf_url": f"https://arxiv.org/pdf/{_sanitize_arxiv_id(result.entry_id)}.pdf",
            },
        )
        candidates.append(candidate)

        time.sleep(max(fetch_cfg.request_interval, 0.0))

    return candidates
