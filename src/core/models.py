"""Dataclasses shared across the pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass(slots=True)
class TopicQuery:
    """Query configuration for a topic."""

    categories: List[str] = field(default_factory=list)
    include_keywords: List[str] = field(default_factory=list)
    exclude_keywords: List[str] = field(default_factory=list)


@dataclass(slots=True)
class TopicTask:
    """Definition of a single topic-driven fetch job."""

    name: str
    label: str
    query: TopicQuery
    interest_prompt: str


@dataclass(slots=True)
class PaperCandidate:
    """Raw paper metadata fetched from arXiv before filtering."""

    arxiv_id: str
    title: str
    abstract: str
    authors: List[str]
    categories: List[str]
    published: Optional[datetime] = None
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RelevanceScore:
    """Multi-dimensional relevance scoring result."""

    dimensions: Dict[str, float]
    weighted_score: float
    decision: str


@dataclass(slots=True)
class PaperSummary:
    """Final structured summary for a paper."""

    arxiv_id: str
    title: str
    topic: str
    todo: List[str]
    findings: List[str]
    conclusion: str
    markdown: str
    score: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
