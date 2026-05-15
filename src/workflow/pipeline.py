"""Pipeline orchestration logic."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Iterable, List, Optional, Set, Tuple

from core.config_loader import load_pipeline_config
from core.models import (
	PaperCandidate,
	PaperSummary,
	PipelineConfig,
	PipelineResult,
	PipelineStats,
	ScoredPaper,
	TopicConfig,
	TopicQuery,
)
from fetchers.ar5iv_parser import Ar5ivParser
from fetchers.arxiv_client import ArxivClient
from filters.relevance_ranker import RelevanceRanker
from publisher.email_digest import EmailDigest
from summaries.report_builder import ReportBuilder
from summaries.task_planner import TaskPlanner
from summaries.task_reader import TaskReader


@dataclass
class PipelineOverrides:
	mode: Optional[str] = None
	paper_limit: Optional[int] = None
	email_enabled: Optional[bool] = None
	# Backfill mode: when both dates are set, the pipeline iterates over chunks
	# of `chunk_days` and merges output into existing site/ instead of wiping.
	start_date: Optional[datetime] = None
	end_date: Optional[datetime] = None
	chunk_days: int = 7
	# When True, only fetch + count candidates per window; skip relevance
	# scoring and TaskReader.analyse entirely. Used to preview cost before
	# committing to a real backfill.
	dry_run: bool = False


def run_pipeline(config_path: str, overrides: Optional[PipelineOverrides] = None) -> PipelineResult:
	config = load_pipeline_config(config_path)

	if overrides:
		if overrides.mode:
			config.runtime.mode = overrides.mode
		if overrides.paper_limit is not None:
			config.runtime.paper_limit = overrides.paper_limit
		if overrides.email_enabled is not None:
			config.email.enabled = overrides.email_enabled

	# Determine fetch windows. Backfill mode if both dates are present.
	backfill = bool(overrides and overrides.start_date and overrides.end_date)
	if backfill:
		windows = _split_windows(
			overrides.start_date,
			overrides.end_date,
			max(1, overrides.chunk_days),
		)
		print(f"[INFO] Backfill mode: {len(windows)} window(s) of ~{overrides.chunk_days} day(s) each")
	else:
		windows = [(None, None)]

	dry_run = bool(overrides and overrides.dry_run)
	if dry_run:
		print("[INFO] DRY-RUN: will fetch candidates and count only; no LLM calls.")

	arxiv_client = ArxivClient(fetch_config=config.fetch)
	ranker = RelevanceRanker(config.openai, config.relevance, mode=config.runtime.mode)
	parser = Ar5ivParser()
	# planner kept for backwards-compat side-effects, even though the new
	# analyse() flow does not consume its output.
	planner = TaskPlanner(config.openai, config.summarization, mode=config.runtime.mode)
	reader = TaskReader(parser, config.openai, config.summarization, mode=config.runtime.mode)
	report_builder = ReportBuilder(config.summarization)
	# site.base_url now points at the Vercel app — used to build "view full
	# report" links inside the weekly email digest.
	email_digest = EmailDigest(
		config.email, config.site.base_url, language=config.openai.language
	)

	# Mirror every freshly built summary into ``data/`` as JSON. The wrapping
	# GitHub Actions workflow will `git commit` and push these files so the
	# Vercel front-end picks them up on next deploy.
	file_store = _build_file_store()
	try:
		file_store.init_schema()
		print(f"[INFO] File-based storage enabled at {file_store.data_dir}")
	except Exception as exc:
		print(f"[WARN] File-storage init failed: {exc}")
		file_store = None

	# Build the set of arxiv_ids already present in data/ so the expensive
	# LLM analysis is skipped for papers we've already processed. Used in
	# backfill mode; harmless (empty) in normal mode.
	seen_ids: Set[str] = set()
	if backfill and file_store is not None:
		seen_ids = {
			str(entry.get("arxiv_id"))
			for entry in file_store.list_recent_analyses(limit=100000)
			if entry.get("arxiv_id")
		}
		print(f"[INFO] Loaded {len(seen_ids)} existing arxiv_ids from data/ for dedup")

	start_time = datetime.utcnow()
	summaries: List[PaperSummary] = []
	total_fetched = 0
	total_selected = 0
	dryrun_counts: List[Tuple[str, str, int]] = []  # (window, topic, count)

	for win_idx, (win_start, win_end) in enumerate(windows, start=1):
		if backfill:
			print(
				f"[INFO] === Window {win_idx}/{len(windows)}: "
				f"{win_start.date()} → {win_end.date()} ==="
			)

		for topic_index, topic in enumerate(config.topics, start=1):
			print(
				f"[INFO] ({topic_index}/{len(config.topics)}) Fetching papers for topic: {topic.label}"
			)
			candidates = arxiv_client.fetch_for_topic(
				topic, start_date=win_start, end_date=win_end
			)
			total_fetched += len(candidates)

			# Deduplicate against earlier windows in this run AND existing manifest.
			before_dedup = len(candidates)
			candidates = [c for c in candidates if c.arxiv_id not in seen_ids]
			if before_dedup - len(candidates) > 0:
				print(
					f"[INFO] Topic {topic.label}: deduped {before_dedup - len(candidates)} already-processed papers"
				)
			print(f"[INFO] Topic {topic.label}: {len(candidates)} new candidates")

			if dry_run:
				dryrun_counts.append(
					(
						f"{win_start.date()}→{win_end.date()}" if backfill else "current",
						topic.label,
						len(candidates),
					)
				)
				# Reserve their IDs so we don't double-count across windows.
				seen_ids.update(c.arxiv_id for c in candidates)
				continue

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
				core_summary, tasks, findings, brief_summary, _, relevance, figure, translations = reader.analyse(
					scored_paper.paper,
					topic.interest_prompt,
				)
				summary = report_builder.build(
					topic=topic,
					scored_paper=scored_paper,
					core_summary=core_summary,
					task_list=tasks,
					findings=findings,
					brief_summary=brief_summary,
					relevance=relevance,
					figure=figure,
					translations=translations,
				)
				summaries.append(summary)
				seen_ids.add(summary.paper.arxiv_id)
				if file_store is not None:
					try:
						file_store.upsert_analysis(
							summary,
							payload=_summary_to_payload(summary, markdown=""),
							model=config.openai.summarization_model,
						)
					except Exception as exc:
						print(f"[WARN] file-storage write failed for {summary.paper.arxiv_id}: {exc}")
				print(
					f"[INFO] Topic {topic.label}: completed summary for {scored_paper.paper.arxiv_id}, total summaries {len(summaries)}"
				)

	if dry_run:
		print("\n[INFO] DRY-RUN summary (papers that WOULD be processed):")
		for win, topic_label, cnt in dryrun_counts:
			print(f"  [{win}] {topic_label}: {cnt}")
		total = sum(cnt for _, _, cnt in dryrun_counts)
		print(f"  TOTAL: {total} unique candidate papers across all windows")
		end_time = datetime.utcnow()
		stats = PipelineStats(
			start_time=start_time,
			end_time=end_time,
			topics_processed=len(config.topics),
			papers_fetched=total_fetched,
			papers_selected=0,
		)
		return PipelineResult(summaries=[], stats=stats)

	# Analyses are already written to data/*.json by file_store inside the
	# topic loop above; the wrapping workflow commits them. There is no
	# static-site render step any more — the Vercel app reads data/ directly.
	print(f"[INFO] Wrote {len(summaries)} analyses to data/.")

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


def _split_windows(
	start: datetime, end: datetime, chunk_days: int
) -> List[Tuple[datetime, datetime]]:
	"""Split [start, end] into back-to-back chunks of `chunk_days`.

	The last chunk is truncated to ``end`` if the range is not evenly divisible.
	"""

	windows: List[Tuple[datetime, datetime]] = []
	cursor = start
	step = timedelta(days=chunk_days)
	while cursor < end:
		nxt = min(cursor + step, end)
		windows.append((cursor, nxt))
		cursor = nxt
	return windows or [(start, end)]


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


# ---------------------------------------------------------------------------
# Single-paper "analyse-one" path (used by the Vercel URL-ingest workflow)
# ---------------------------------------------------------------------------


@dataclass
class AnalyseOneResult:
	"""Return value of :func:`run_analyse_one`."""

	summary: PaperSummary
	payload: dict  # JSON-serialisable dict — the data/analyses/<id>.json shape


def run_analyse_one(
	config_path: str,
	arxiv_id: str,
	topic_name: Optional[str] = None,
	write_db: bool = False,
) -> AnalyseOneResult:
	"""Fetch + analyse a single arXiv paper and return the structured result.

	When ``write_db`` is True the resulting analysis is written to
	``data/analyses/<id>.json`` (and the slim ``data/index.json`` is updated).
	The wrapping ``analyse-one.yml`` workflow then commits those files; Vercel
	auto-redeploys and the Next.js app serves the new analysis.
	"""

	config = load_pipeline_config(config_path)

	# Resolve which topic context to use.
	topic = _resolve_topic_for_one(config, topic_name)

	# Fetch paper metadata via the arXiv API id_list endpoint.
	arxiv_client = ArxivClient(fetch_config=config.fetch)
	paper = arxiv_client.fetch_one(arxiv_id, topic=topic)
	if paper is None:
		raise RuntimeError(f"arXiv ID '{arxiv_id}' could not be fetched")
	print(f"[INFO] analyse-one: fetched [{paper.arxiv_id}] {paper.title}")

	# Score relevance the same way the weekly pipeline does. A manually
	# submitted paper isn't automatically relevant — the user still wants an
	# honest "how well does this match my interests" number.
	ranker = RelevanceRanker(config.openai, config.relevance, mode=config.runtime.mode)
	scored = ranker.score(topic, [paper])
	scored_paper = scored[0] if scored else ScoredPaper(
		paper=paper, scores=[], total_score=0.0,
	)

	parser = Ar5ivParser()
	reader = TaskReader(parser, config.openai, config.summarization, mode=config.runtime.mode)
	core_summary, tasks, findings, brief_summary, markdown, relevance, figure, translations = reader.analyse(
		paper, topic.interest_prompt
	)

	report_builder = ReportBuilder(config.summarization)
	summary = report_builder.build(
		topic=topic,
		scored_paper=scored_paper,
		core_summary=core_summary,
		task_list=tasks,
		findings=findings,
		brief_summary=brief_summary,
		relevance=relevance,
		figure=figure,
		translations=translations,
	)

	payload = _summary_to_payload(summary, markdown=markdown)

	if write_db:
		_try_write_to_storage(summary, payload, model=config.openai.summarization_model)

	return AnalyseOneResult(summary=summary, payload=payload)


def _resolve_topic_for_one(config: PipelineConfig, topic_name: Optional[str]) -> TopicConfig:
	if topic_name:
		for t in config.topics:
			if t.name == topic_name or t.label == topic_name:
				return t
		print(
			f"[WARN] Topic '{topic_name}' not found in config; falling back to first topic"
		)
	if config.topics:
		return config.topics[0]
	# No topics in config — manufacture an empty placeholder so analyse() works.
	return TopicConfig(
		name="ad-hoc", label="Ad-hoc submission",
		query=TopicQuery(), interest_prompt="",
	)


def _bi(en_text: str, zh_text: Optional[str]) -> dict:
	"""A bilingual text field: ``{"en": ..., "zh": ...}``.

	Analysis is generated in English; ``zh`` is the translation when one was
	produced, otherwise it mirrors ``en`` so the web side always has both
	keys and can fall back cleanly.
	"""
	en_text = en_text or ""
	return {"en": en_text, "zh": (zh_text or en_text)}


def _summary_to_payload(summary: PaperSummary, markdown: str) -> dict:
	"""Serialise a PaperSummary into a JSON-friendly dict for storage.

	Every user-facing text field is bilingual ``{en, zh}``. See
	:func:`_bi` and ``PaperSummary.translations``.
	"""

	paper = summary.paper
	tr = summary.translations or {}
	tr_core = tr.get("core_summary") or {}
	tr_findings = tr.get("findings") or []

	def _tf(i: int) -> dict:
		return tr_findings[i] if i < len(tr_findings) else {}

	return {
		"arxiv_id": paper.arxiv_id,
		"topic": summary.topic.name,
		"topic_label": summary.topic.label,
		"title": paper.title,
		"authors": list(paper.authors or []),
		"affiliations": list(paper.affiliations or []),
		"categories": list(paper.categories or []),
		"published": paper.published.isoformat() if paper.published else None,
		"updated": paper.updated.isoformat() if paper.updated else None,
		"abstract": paper.abstract,
		"arxiv_url": paper.arxiv_url,
		"pdf_url": paper.pdf_url,
		"comment": paper.comment,
		"relevance": _bi(summary.relevance, tr.get("relevance")),
		"figure": (
			{
				"label": summary.figure.label,
				"caption": _bi(summary.figure.caption, tr.get("figure_caption")),
				"url": summary.figure.url,
				"reference_text": summary.figure.reference_text,
			}
			if summary.figure else None
		),
		"brief_summary": _bi(summary.brief_summary, tr.get("brief_summary")),
		"core_summary": (
			{
				"problem": _bi(summary.core_summary.problem, tr_core.get("problem")),
				"solution": _bi(summary.core_summary.solution, tr_core.get("solution")),
				"methodology": _bi(summary.core_summary.methodology, tr_core.get("methodology")),
				"experiments": _bi(summary.core_summary.experiments, tr_core.get("experiments")),
				"conclusion": _bi(summary.core_summary.conclusion, tr_core.get("conclusion")),
			}
			if summary.core_summary else None
		),
		"tasks": [
			{
				"question": _bi(t.question, _tf(i).get("question")),
				"reason": _bi(t.reason, _tf(i).get("reason")),
			}
			for i, t in enumerate(summary.task_list)
		],
		"findings": [
			{
				"question": _bi(f.task.question, _tf(i).get("question")),
				"reason": _bi(f.task.reason, _tf(i).get("reason")),
				"answer": _bi(f.answer, _tf(i).get("answer")),
				"confidence": f.confidence,
			}
			for i, f in enumerate(summary.findings)
		],
		"score": _normalise_score(summary.score_details),
		"score_dimensions": [
			{"name": s.name, "weight": s.weight, "value": s.value}
			for s in summary.score_details.scores
		],
		"markdown": markdown,
	}


def _normalise_score(scored: ScoredPaper) -> float:
	total_w = sum(s.weight for s in scored.scores) or 1.0
	return (sum(s.weight * s.value for s in scored.scores) / total_w) * 100


def _build_file_store():
	"""Return a GitFileStore. Never fails — the underlying directory is
	created on first write."""
	from storage.git_files import GitFileStore  # type: ignore
	return GitFileStore.from_env()


def _try_write_to_storage(summary: PaperSummary, payload: dict, model: Optional[str] = None) -> None:
	"""Write the analysis to ``data/`` as JSON files. Replaces the old
	Postgres dual-write path. Files are committed to git by the workflow
	that wraps this pipeline; locally this just touches the filesystem.
	"""
	try:
		store = _build_file_store()
		store.init_schema()
		store.upsert_paper(summary.paper)
		store.upsert_analysis(summary, payload=payload, model=model)
		print(
			f"[INFO] analyse-one: wrote {summary.paper.arxiv_id} to "
			f"data/analyses/{summary.paper.arxiv_id}.json"
		)
	except Exception as exc:  # pragma: no cover
		print(f"[WARN] File-based storage write failed: {exc}")
