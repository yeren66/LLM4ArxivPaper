"""Top-level pipeline orchestration."""

from __future__ import annotations

import logging
from typing import List

from core.config_loader import PipelineConfig
from core.models import PaperSummary
from fetchers.arxiv_client import fetch_candidates
from filters.relevance_ranker import rank_candidates
from publisher.email_digest import send_digest
from publisher.static_site import build_site
from summaries.report_builder import build_summary
from summaries.task_planner import build_todo_list
from summaries.task_reader import answer_questions

LOGGER = logging.getLogger(__name__)


def run_pipeline(config: PipelineConfig) -> List[PaperSummary]:
    """Execute the end-to-end processing pipeline."""

    summaries: List[PaperSummary] = []

    for task in config.topics:
        LOGGER.info("Fetching candidates for topic %s", task.name)
        candidates = fetch_candidates(task, config.fetch)
        if not candidates:
            LOGGER.info("No candidates fetched for topic %s", task.name)
            continue

        ranked = rank_candidates(task, candidates, config.relevance)
        for paper, score in ranked:
            if score.decision != "include":
                continue

            todo = build_todo_list(
                paper,
                desired_length=config.summarization.task_list_size,
                interest_prompt=task.interest_prompt,
            )

            question_limit = config.summarization.max_sections
            questions_for_answers = todo[:question_limit] if question_limit else todo
            answers = answer_questions(paper, questions_for_answers)
            findings = [
                f"{question} -> {answer}" for question, answer in zip(questions_for_answers, answers)
            ]

            summary = build_summary(
                paper,
                todo=todo,
                findings=findings,
                topic_label=task.label,
                score=score.weighted_score,
            )
            summaries.append(summary)

    if summaries:
        LOGGER.info("Generating static site with %d summaries", len(summaries))
        build_site(config.site, summaries)
    else:
        LOGGER.info("No summaries generated; skipping site build")

    try:
        send_digest(config.email, summaries)
    except Exception as exc:  # pragma: no cover - best effort notification
        LOGGER.warning("Failed to send email digest: %s", exc)

    return summaries
