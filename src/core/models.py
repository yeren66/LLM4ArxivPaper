"""Core datamodels used across the LLM4ArxivPaper pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional


# ---------------------------------------------------------------------------
# Configuration dataclasses
# ---------------------------------------------------------------------------


@dataclass
class RelevanceDimension:
	"""Single scoring dimension for relevance evaluation."""

	name: str
	weight: float
	description: Optional[str] = None


@dataclass
class TopicQuery:
	"""Query definition for fetching arXiv papers."""

	categories: List[str] = field(default_factory=list)
	include: List[str] = field(default_factory=list)
	exclude: List[str] = field(default_factory=list)


@dataclass
class TopicConfig:
	"""Topic level configuration."""

	name: str
	label: str
	query: TopicQuery
	interest_prompt: str


@dataclass
class OpenAIConfig:
	api_key: Optional[str]
	base_url: Optional[str]
	relevance_model: str
	summarization_model: str
	temperature: float = 0.2


@dataclass
class FetchConfig:
	max_papers_per_topic: int
	days_back: int
	request_delay: float = 1.0


@dataclass
class RelevanceConfig:
	dimensions: List[RelevanceDimension]
	pass_threshold: float


@dataclass
class SummarizationConfig:
	task_list_size: int
	max_sections: int


@dataclass
class SiteConfig:
	output_dir: str
	base_url: str


@dataclass
class EmailConfig:
	enabled: bool = False
	sender: Optional[str] = None
	recipients: List[str] = field(default_factory=list)
	subject_template: str = "每周论文雷达 - {run_date}"


@dataclass
class RuntimeConfig:
	mode: str = "offline"
	topic_limit: Optional[int] = None
	paper_limit: Optional[int] = None


@dataclass
class PipelineConfig:
	openai: OpenAIConfig
	fetch: FetchConfig
	topics: List[TopicConfig]
	relevance: RelevanceConfig
	summarization: SummarizationConfig
	site: SiteConfig
	email: EmailConfig
	runtime: RuntimeConfig

	@staticmethod
	def from_dict(payload: Dict[str, Any]) -> "PipelineConfig":
		topics = [
			TopicConfig(
				name=item["name"],
				label=item.get("label", item["name"].title()),
				query=TopicQuery(
					categories=list(item.get("query", {}).get("categories", [])),
					include=list(item.get("query", {}).get("include", [])),
					exclude=list(item.get("query", {}).get("exclude", [])),
				),
				interest_prompt=item.get("interest_prompt", ""),
			)
			for item in payload.get("topics", [])
		]

		dimensions = [
			RelevanceDimension(
				name=d["name"],
				weight=float(d.get("weight", 0.0)),
				description=d.get("description"),
			)
			for d in payload.get("relevance", {}).get("scoring_dimensions", [])
		]

		openai_section = payload.get("openai", {})
		fetch_section = payload.get("fetch", {})
		relevance_section = payload.get("relevance", {})
		summarization_section = payload.get("summarization", {})
		site_section = payload.get("site", {})
		email_section = payload.get("email", {})
		runtime_section = payload.get("runtime", {})

		return PipelineConfig(
			openai=OpenAIConfig(
				api_key=openai_section.get("api_key"),
				base_url=openai_section.get("base_url") or None,
				relevance_model=openai_section.get("relevance_model", "gpt-4o-mini"),
				summarization_model=openai_section.get("summarization_model", "gpt-4o-mini"),
				temperature=float(openai_section.get("temperature", 0.2)),
			),
			fetch=FetchConfig(
				max_papers_per_topic=int(fetch_section.get("max_papers_per_topic", 25)),
				days_back=int(fetch_section.get("days_back", 7)),
				request_delay=float(fetch_section.get("request_delay", 1.0)),
			),
			topics=topics,
			relevance=RelevanceConfig(
				dimensions=dimensions,
				pass_threshold=float(relevance_section.get("pass_threshold", 60.0)),
			),
			summarization=SummarizationConfig(
				task_list_size=int(summarization_section.get("task_list_size", 5)),
				max_sections=int(summarization_section.get("max_sections", 4)),
			),
			site=SiteConfig(
				output_dir=site_section.get("output_dir", "site"),
				base_url=site_section.get("base_url", ""),
			),
			email=EmailConfig(
				enabled=bool(email_section.get("enabled", False)),
				sender=email_section.get("sender"),
				recipients=list(email_section.get("recipients", [])),
				subject_template=email_section.get("subject_template", "每周论文雷达 - {run_date}"),
			),
			runtime=RuntimeConfig(
				mode=runtime_section.get("mode", "offline"),
				topic_limit=runtime_section.get("topic_limit"),
				paper_limit=runtime_section.get("paper_limit"),
			),
		)


# ---------------------------------------------------------------------------
# Runtime data models
# ---------------------------------------------------------------------------


@dataclass
class PaperCandidate:
	topic: TopicConfig
	arxiv_id: str
	title: str
	abstract: str
	authors: List[str]
	categories: List[str]
	published: datetime
	updated: datetime
	arxiv_url: str
	pdf_url: Optional[str] = None


@dataclass
class DimensionScore:
	name: str
	weight: float
	value: float


@dataclass
class ScoredPaper:
	paper: PaperCandidate
	scores: List[DimensionScore]
	total_score: float

	def to_dict(self) -> Dict[str, Any]:
		return {
			"arxiv_id": self.paper.arxiv_id,
			"title": self.paper.title,
			"total_score": self.total_score,
			"scores": [score.__dict__ for score in self.scores],
		}


@dataclass
class TaskItem:
	question: str
	reason: str


@dataclass
class TaskFinding:
	task: TaskItem
	answer: str
	confidence: float


@dataclass
class PaperSummary:
	paper: PaperCandidate
	topic: TopicConfig
	task_list: List[TaskItem]
	findings: List[TaskFinding]
	overview: str
	score_details: ScoredPaper
	markdown: str


@dataclass
class PipelineStats:
	start_time: datetime
	end_time: datetime
	topics_processed: int
	papers_fetched: int
	papers_selected: int


@dataclass
class PipelineResult:
	summaries: List[PaperSummary]
	stats: PipelineStats


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def limit_items(items: Iterable[Any], limit: Optional[int]) -> List[Any]:
	"""Return at most `limit` items from the iterable."""

	materialised = list(items)
	if limit is None:
		return materialised
	return materialised[:limit]
