"""Heuristic relevance scoring for paper candidates."""

from __future__ import annotations

import re
from collections import Counter
from typing import Dict, List, Sequence, Tuple

from core.config_loader import RelevanceConfig
from core.models import PaperCandidate, RelevanceScore, TopicTask


TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    return [token for token in TOKEN_RE.sub(" ", text.lower()).split() if token]


def _overlap_ratio(a: Sequence[str], b: Sequence[str]) -> float:
    if not a or not b:
        return 0.0
    counter_a = Counter(a)
    counter_b = Counter(b)
    overlap = sum((counter_a & counter_b).values())
    total = sum(counter_a.values()) or 1
    return min(1.0, overlap / total)


def _score_dimension(name: str, task: TopicTask, paper: PaperCandidate, tokens: List[str]) -> float:
    text = " ".join(tokens)

    if name == "topic_alignment":
        keywords = [kw.lower() for kw in task.query.include_keywords]
        prompt_tokens = _tokenize(task.interest_prompt)
        ratio_kw = _overlap_ratio(tokens, keywords)
        ratio_prompt = _overlap_ratio(tokens, prompt_tokens)
        return max(ratio_kw, ratio_prompt) * 100

    if name == "methodology_fit":
        method_words = ["method", "approach", "framework", "architecture", "technique", "方法", "模型"]
        hits = sum(1 for word in method_words if word in text)
        return min(100.0, hits * 20)

    if name == "novelty":
        novelty_words = ["novel", "new", "first", "innovative", "首次", "创新"]
        hits = sum(1 for word in novelty_words if word in text)
        return 40.0 + min(60.0, hits * 15)

    if name == "experiment_depth":
        experiment_words = ["experiment", "evaluation", "dataset", "benchmark", "实验", "评估", "结果"]
        hits = sum(1 for word in experiment_words if word in text)
        return min(100.0, hits * 25)

    prompt_tokens = _tokenize(task.interest_prompt)
    return _overlap_ratio(tokens, prompt_tokens) * 100


def rank_candidates(
    task: TopicTask,
    candidates: List[PaperCandidate],
    relevance_cfg: RelevanceConfig,
) -> List[Tuple[PaperCandidate, RelevanceScore]]:
    """Assign heuristic relevance scores and return sorted results."""

    dimensions = relevance_cfg.dimensions or []
    if not dimensions:
        from core.config_loader import RelevanceDimension

        dimensions = [
            RelevanceDimension("topic_alignment", 0.5),
            RelevanceDimension("methodology_fit", 0.25),
            RelevanceDimension("experiment_depth", 0.25),
        ]

    total_weight = sum(d.weight for d in dimensions) or 1.0
    scored: List[Tuple[PaperCandidate, RelevanceScore]] = []

    for paper in candidates:
        tokens = _tokenize(paper.title + " " + paper.abstract)
        dim_scores: Dict[str, float] = {}
        for dim in dimensions:
            dim_scores[dim.name] = _score_dimension(dim.name, task, paper, tokens)

        weighted_total = sum(dim_scores[dim.name] * dim.weight for dim in dimensions) / total_weight
        decision = "include" if weighted_total >= relevance_cfg.pass_threshold else "skip"
        scored.append((paper, RelevanceScore(dimensions=dim_scores, weighted_score=weighted_total, decision=decision)))

    scored.sort(key=lambda item: item[1].weighted_score, reverse=True)
    return scored
