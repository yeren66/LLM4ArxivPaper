"""Pipeline orchestration logic."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional

from core.config_loader import load_pipeline_config
from core.models import (
	PaperCandidate,
	PaperSummary,
	PipelineConfig,
	PipelineResult,
	PipelineStats,
	ScoredPaper,
	TopicConfig,
)
from fetchers.ar5iv_parser import Ar5ivParser
from fetchers.arxiv_client import ArxivClient
from filters.relevance_ranker import RelevanceRanker
from publisher.email_digest import EmailDigest
from publisher.static_site import StaticSiteBuilder
from summaries.report_builder import ReportBuilder
from summaries.task_planner import TaskPlanner
from summaries.task_reader import TaskReader


@dataclass
class PipelineOverrides:
	mode: Optional[str] = None
	paper_limit: Optional[int] = None
	email_enabled: Optional[bool] = None


def run_pipeline(config_path: str, overrides: Optional[PipelineOverrides] = None) -> PipelineResult:
	config = load_pipeline_config(config_path)

	if overrides:
		if overrides.mode:
			config.runtime.mode = overrides.mode
		if overrides.paper_limit is not None:
			config.runtime.paper_limit = overrides.paper_limit
		if overrides.email_enabled is not None:
			config.email.enabled = overrides.email_enabled

	arxiv_client = ArxivClient(fetch_config=config.fetch)
	ranker = RelevanceRanker(config.openai, config.relevance, mode=config.runtime.mode)
	parser = Ar5ivParser()
	planner = TaskPlanner(config.openai, config.summarization, mode=config.runtime.mode)
	reader = TaskReader(parser, config.openai, config.summarization, mode=config.runtime.mode)
	report_builder = ReportBuilder(config.summarization)
	site_builder = StaticSiteBuilder(config.site)
	email_digest = EmailDigest(config.email, config.site.base_url)

	start_time = datetime.utcnow()
	summaries: List[PaperSummary] = []
	total_fetched = 0
	total_selected = 0

	for topic_index, topic in enumerate(config.topics, start=1):
		print(f"[INFO] ({topic_index}/{len(config.topics)}) Fetching papers for topic: {topic.label}")
		candidates = arxiv_client.fetch_for_topic(topic)
		total_fetched += len(candidates)
		print(f"[INFO] Topic {topic.label}: fetched {len(candidates)} candidates")

		if not candidates and config.runtime.mode == "offline":
			print("[INFO] No live arXiv results; generating offline demo candidate.")
			candidates = [_build_offline_demo_candidate(topic)]

		if not candidates:
			print(f"[WARN] No candidates available for topic {topic.label}; skipping.")
			continue

		if config.runtime.paper_limit is not None:
			candidates = candidates[: config.runtime.paper_limit]
			print(
				f"[INFO] Topic {topic.label}: applying paper limit {config.runtime.paper_limit}, using {len(candidates)} candidates"
			)

		scored = ranker.score(topic, candidates)
		selected = _filter_by_threshold(scored, config)
		print(
			f"[INFO] Topic {topic.label}: scored {len(scored)} papers, {len(selected)} passed threshold {config.relevance.pass_threshold}"
		)
		total_selected += len(selected)

		total_weight = sum(dim.weight for dim in config.relevance.dimensions) or 1.0
		for paper_index, scored_paper in enumerate(selected, start=1):
			normalised_score = (scored_paper.total_score / total_weight) * 100
			print(
				f"[INFO] Topic {topic.label}: processing paper {paper_index}/{len(selected)} "
				f"[{scored_paper.paper.arxiv_id}] {scored_paper.paper.title} — score {normalised_score:.1f}"
			)
			# New workflow: pass interest_prompt instead of pre-built tasks
			core_summary, tasks, findings, overview, brief_summary, _ = reader.analyse(
				scored_paper.paper, 
				topic.interest_prompt
			)
			summary = report_builder.build(
				topic=topic,
				scored_paper=scored_paper,
				core_summary=core_summary,
				task_list=tasks,
				findings=findings,
				overview=overview,
				brief_summary=brief_summary,
			)
			summaries.append(summary)
			print(
				f"[INFO] Topic {topic.label}: completed summary for {scored_paper.paper.arxiv_id}, total summaries {len(summaries)}"
			)

	os.environ["PIPELINE_RUN_AT"] = datetime.utcnow().isoformat()
	site_builder.build(summaries)
	print(f"[INFO] Static site written to '{config.site.output_dir}'.")

	subject_context = {
		"run_date": datetime.utcnow().strftime("%Y-%m-%d"),
		"paper_count": len(summaries),
	}
	email_digest.send(summaries, subject_context)

	end_time = datetime.utcnow()
	stats = PipelineStats(
		start_time=start_time,
		end_time=end_time,
		topics_processed=len(config.topics),
		papers_fetched=total_fetched,
		papers_selected=total_selected,
	)

	return PipelineResult(summaries=summaries, stats=stats)


def _filter_by_threshold(scored_papers: Iterable[ScoredPaper], config: PipelineConfig) -> List[ScoredPaper]:
	total_weight = sum(dim.weight for dim in config.relevance.dimensions) or 1.0
	selected: List[ScoredPaper] = []
	for scored in scored_papers:
		normalised = (scored.total_score / total_weight) * 100
		if normalised >= config.relevance.pass_threshold:
			selected.append(scored)
	return selected


def _build_offline_demo_candidate(topic: TopicConfig) -> PaperCandidate:
	now = datetime.utcnow()
	keywords = topic.query.include or [topic.label]
	categories = topic.query.categories or ["cs.AI"]
	keyword_str = ", ".join(keywords)
	category_str = ", ".join(categories)
	abstract = (
		f"This is offline demo data for pipeline verification. Focused topic: {topic.label}."
		f" The paper explores directions around {keyword_str}, emphasizing novel methods and experimental design."
		f" Applicable arXiv categories include {category_str}, facilitating automated workflow testing."
	)
	return PaperCandidate(
		topic=topic,
		arxiv_id=f"demo-{topic.name}-{now.strftime('%H%M%S')}",
		title=f"[Demo] {topic.label} Automated Test Example",
		abstract=abstract,
		authors=["LLM4ArxivPaper Bot"],
		affiliations=["LLM4ArxivPaper Project"],
		categories=categories,
		published=now,
		updated=now,
		arxiv_url="https://arxiv.org/abs/0000.00000",
		pdf_url=None,
	)
