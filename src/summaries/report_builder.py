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
		core_summary,  # CoreSummary or None
		task_list: List[TaskItem],
		findings: List[TaskFinding],
		overview: str,
		brief_summary: str = "",
	) -> PaperSummary:
		paper = scored_paper.paper

		lines: List[str] = []
		lines.append(f"# {paper.title}")
		lines.append("")
		
		# Add brief summary if available
		if brief_summary:
			for paragraph in [p.strip() for p in brief_summary.split("\n\n") if p.strip()]:
				lines.append("> " + paragraph.replace("\n", " "))
			lines.append("")
		
		lines.append("**Topic**: {label}".format(label=topic.label))
		lines.append("**arXiv**: [{id}]({url})".format(id=paper.arxiv_id, url=paper.arxiv_url))
		lines.append("**Authors**: {authors}".format(authors=", ".join(paper.authors)))
		lines.append("**Published**: {date}".format(date=paper.published.strftime("%Y-%m-%d")))
		lines.append("**Score**: {score:.1f}".format(score=self._normalised_score(scored_paper)))
		lines.append("")

		# Add scoring breakdown
		lines.append("### 📊 Relevance Scores")
		for score in scored_paper.scores:
			normalized = (score.value * 100)
			lines.append(f"- **{score.name}**: {normalized:.1f}/100 (weight: {score.weight:.2f})")
		lines.append("")

		# Add core summary (5 aspects) if available
		if core_summary:
			lines.append("## � 论文核心内容")
			lines.append("")
			lines.append("### 1. 主要解决了什么问题？")
			lines.append(core_summary.problem)
			lines.append("")
			lines.append("### 2. 提出了什么解决方案？")
			lines.append(core_summary.solution)
			lines.append("")
			lines.append("### 3. 核心方法/步骤/策略")
			lines.append(core_summary.methodology)
			lines.append("")
			lines.append("### 4. 实验设计")
			lines.append(core_summary.experiments)
			lines.append("")
			lines.append("### 5. 结论")
			lines.append(core_summary.conclusion)
			lines.append("")

		lines.append("## 🤔 用户关心的问题")
		for idx, task in enumerate(task_list, start=1):
			lines.append(f"{idx}. **{task.question}** - {task.reason}")
		lines.append("")

		lines.append("## 逐项解答")
		for finding in findings:
			lines.append(f"### {finding.task.question}")
			lines.append(finding.answer.strip())
			lines.append(f"*Confidence: {finding.confidence:.2f}*\n")

		lines.append("## 📝 综合总结")
		lines.append(overview.strip() or paper.abstract.strip())
		lines.append("")

		lines.append("## 💡 为什么推荐这篇论文?")
		recommendation = self._generate_recommendation(topic, scored_paper, findings)
		lines.append(recommendation)
		lines.append("")

		lines.append("---")
		lines.append("*Generated at {timestamp}*".format(timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")))

		markdown = "\n".join(lines)

		return PaperSummary(
			paper=paper,
			topic=topic,
			core_summary=core_summary,
			task_list=task_list,
			findings=findings,
			overview=overview,
			score_details=scored_paper,
			markdown=markdown,
			brief_summary=brief_summary,
		)

	@staticmethod
	def _normalised_score(scored_paper: ScoredPaper) -> float:
		total_weight = sum(score.weight for score in scored_paper.scores) or 1.0
		weighted_value = sum(score.weight * score.value for score in scored_paper.scores)
		return (weighted_value / total_weight) * 100

	@staticmethod
	def _generate_recommendation(topic: TopicConfig, scored_paper: ScoredPaper, findings: List[TaskFinding]) -> str:
		"""Generate a recommendation explaining why this paper is relevant to the user."""
		
		# Find the highest scoring dimension
		top_dimension = max(scored_paper.scores, key=lambda x: x.value * x.weight) if scored_paper.scores else None
		
		# Extract key insight from findings
		high_confidence_findings = [f for f in findings if f.confidence > 0.6]
		key_insight = high_confidence_findings[0].answer[:200] if high_confidence_findings else ""
		
		if top_dimension:
			normalized_score = (top_dimension.value * 100)
			recommendation = (
				f"This paper scores high in the **{top_dimension.name}** dimension ({normalized_score:.1f}/100), "
				f"highly aligned with your research interests in {topic.label}."
			)
			if key_insight:
				recommendation += f" {key_insight}..."
		else:
			recommendation = f"This paper is relevant to your research direction in {topic.label}, recommended for further reading."
		
		return recommendation
