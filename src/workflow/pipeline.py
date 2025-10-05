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
	topic_limit: Optional[int] = None
	paper_limit: Optional[int] = None
	email_enabled: Optional[bool] = None


def run_pipeline(config_path: str, overrides: Optional[PipelineOverrides] = None) -> PipelineResult:
	config = load_pipeline_config(config_path)

	if overrides:
		if overrides.mode:
			config.runtime.mode = overrides.mode
		if overrides.topic_limit is not None:
			config.runtime.topic_limit = overrides.topic_limit
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

	topics = config.topics
	if config.runtime.topic_limit is not None:
		topics = topics[: config.runtime.topic_limit]

	for topic in topics:
		print(f"[INFO] Fetching papers for topic: {topic.label}")
		candidates = arxiv_client.fetch_for_topic(topic)
		total_fetched += len(candidates)

		if not candidates and config.runtime.mode == "offline":
			print("[INFO] No live arXiv results; generating offline demo candidate.")
			candidates = [_build_offline_demo_candidate(topic)]

		if not candidates:
			print(f"[WARN] No candidates available for topic {topic.label}; skipping.")
			continue

		if config.runtime.paper_limit is not None:
			candidates = candidates[: config.runtime.paper_limit]

		scored = ranker.score(topic, candidates)
		selected = _filter_by_threshold(scored, config)
		total_selected += len(selected)

		for scored_paper in selected:
			tasks = planner.build_tasks(topic, scored_paper.paper)
			findings, overview, _ = reader.analyse(scored_paper.paper, tasks)
			summary = report_builder.build(
				topic=topic,
				scored_paper=scored_paper,
				task_list=tasks,
				findings=findings,
				overview=overview,
			)
			summaries.append(summary)

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
		topics_processed=len(topics),
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
	keyword_str = "、".join(keywords)
	category_str = ", ".join(categories)
	abstract = (
		f"本条目为离线演示数据，用于验证流水线。聚焦主题：{topic.label}。"
		f" 论文围绕 {keyword_str} 等方向展开，强调 novel 方法并提供 experiment 设计。"
		f" 适用的 arXiv 分类包括 {category_str}，便于测试自动化流程。"
	)
	return PaperCandidate(
		topic=topic,
		arxiv_id=f"demo-{topic.name}-{now.strftime('%H%M%S')}",
		title=f"[Demo] {topic.label} 自动化测试示例",
		abstract=abstract,
		authors=["LLM4ArxivPaper Bot"],
		categories=categories,
		published=now,
		updated=now,
		arxiv_url="https://arxiv.org/abs/0000.00000",
		pdf_url=None,
	)
