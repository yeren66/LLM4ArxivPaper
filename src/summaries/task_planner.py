"""Generate TODO-style reading tasks for a paper."""

from __future__ import annotations

import re
from typing import Iterable, List, Optional

from core.models import PaperCandidate


SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？.!?])\s+")


def _normalize_bullet(line: str) -> Optional[str]:
    cleaned = line.strip().strip("-•·*。；; ")
    if not cleaned:
        return None
    return cleaned


def _prompt_tasks(interest_prompt: Optional[str]) -> List[str]:
    if not interest_prompt:
        return []

    tasks: List[str] = []
    for raw_line in interest_prompt.splitlines():
        line = _normalize_bullet(raw_line)
        if not line:
            continue
        if not line.endswith("?"):
            line = f"该论文如何处理：{line}？"
        tasks.append(line)
    return tasks


def _abstract_tasks(abstract: str) -> List[str]:
    tasks: List[str] = []
    for sentence in SENTENCE_SPLIT_RE.split(abstract.strip()):
        sentence = sentence.strip()
        if len(sentence) < 20:
            continue
        if sentence:
            tasks.append(f"分析：{sentence}")
    return tasks


def _authorship_tasks(authors: Iterable[str]) -> List[str]:
    authors_list = list(authors)
    if not authors_list:
        return []
    lead = authors_list[0]
    return [f"了解作者 {lead} 等人的背景与以往工作"]


def build_todo_list(
    paper: PaperCandidate,
    desired_length: int = 5,
    interest_prompt: Optional[str] = None,
) -> List[str]:
    """Assemble a short TODO list mixing prompt-derived and abstract-derived tasks."""

    pool: List[str] = []
    pool.extend(_prompt_tasks(interest_prompt))
    pool.extend(_abstract_tasks(paper.abstract))
    pool.extend(_authorship_tasks(paper.authors))

    deduped: List[str] = []
    seen = set()
    for item in pool:
        normalized = item.strip().rstrip("。！？")
        if normalized and normalized not in seen:
            deduped.append(normalized)
            seen.add(normalized)

    if not deduped:
        deduped.append("阅读论文摘要，提炼关键贡献点")

    return deduped[: max(1, desired_length)]
