"""Assemble final Markdown reports."""

from __future__ import annotations

from datetime import datetime
from typing import List

from core.models import DimensionScore, PaperSummary, ScoredPaper, SummarizationConfig, TaskFinding, TaskItem, TopicConfig


class ReportBuilder:
	def __init__(self, summarization_config: SummarizationConfig):
		self.summarization_config = summarization_config

	def build(
		self,
		topic: TopicConfig,
		scored_paper: ScoredPaper,
		task_list: List[TaskItem],
	findings: List[TaskFinding],
	overview: str,
	) -> PaperSummary:
		paper = scored_paper.paper

		lines: List[str] = []
		lines.append(f"# {paper.title}")
		lines.append("")
		lines.append("**Topic**: {label}".format(label=topic.label))
		lines.append("**arXiv**: [{id}]({url})".format(id=paper.arxiv_id, url=paper.arxiv_url))
		lines.append("**Authors**: {authors}".format(authors=", ".join(paper.authors)))
		lines.append("**Published**: {date}".format(date=paper.published.strftime("%Y-%m-%d")))
		lines.append("**Score**: {score:.1f}".format(score=self._normalised_score(scored_paper)))
		lines.append("")

		lines.append("## 阅读 TODO")
		for idx, task in enumerate(task_list, start=1):
			lines.append(f"{idx}. **{task.question}** - {task.reason}")
		lines.append("")

		lines.append("## 逐项解答")
		for finding in findings:
			lines.append(f"### {finding.task.question}")
			lines.append(finding.answer.strip())
			lines.append(f"*Confidence: {finding.confidence:.2f}*\n")

		lines.append("## 综合总结")
		lines.append(overview.strip() or paper.abstract.strip())
		lines.append("")

		lines.append("---")
		lines.append("*Generated at {timestamp}*".format(timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")))

		markdown = "\n".join(lines)

		return PaperSummary(
			paper=paper,
			topic=topic,
			task_list=task_list,
			findings=findings,
			overview=overview,
			score_details=scored_paper,
			markdown=markdown,
		)

	@staticmethod
	def _normalised_score(scored_paper: ScoredPaper) -> float:
		total_weight = sum(score.weight for score in scored_paper.scores) or 1.0
		weighted_value = sum(score.weight * score.value for score in scored_paper.scores)
		return (weighted_value / total_weight) * 100
