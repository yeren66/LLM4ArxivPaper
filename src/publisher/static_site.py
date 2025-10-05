"""Generate a minimal static site for published summaries."""

from __future__ import annotations

import json
import os
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

from core.models import PaperSummary, SiteConfig


class StaticSiteBuilder:
	def __init__(self, site_config: SiteConfig):
		self.site_config = site_config

	# ------------------------------------------------------------------

	def build(self, summaries: Iterable[PaperSummary]) -> Dict[str, str]:
		output_dir = Path(self.site_config.output_dir)
		if output_dir.exists():
			shutil.rmtree(output_dir)
		output_dir.mkdir(parents=True, exist_ok=True)

		topic_groups: Dict[str, List[PaperSummary]] = defaultdict(list)
		for summary in summaries:
			topic_groups[summary.topic.name].append(summary)

		index_entries = []
		for topic_name, topic_summaries in topic_groups.items():
			topic_dir = output_dir / "topics" / topic_name
			topic_dir.mkdir(parents=True, exist_ok=True)
			for summary in topic_summaries:
				file_name = f"{summary.paper.arxiv_id}.html"
				file_path = topic_dir / file_name
				file_path.write_text(self._render_paper(summary), encoding="utf-8")
			index_entries.append((topic_name, topic_summaries))

		index_path = output_dir / "index.html"
		index_path.write_text(self._render_index(index_entries), encoding="utf-8")

		manifest_path = output_dir / "manifest.json"
		manifest = {
			"base_url": self.site_config.base_url,
			"generated": os.environ.get("PIPELINE_RUN_AT"),
			"topics": {
				topic: [summary.paper.arxiv_id for summary in items]
				for topic, items in topic_groups.items()
			},
		}
		manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

		return {"index": str(index_path)}

	# ------------------------------------------------------------------

	def _render_index(self, index_entries: List[tuple]) -> str:
		base_url = self.site_config.base_url.rstrip("/")
		html_parts = [
			"<!DOCTYPE html>",
			"<html lang='zh-cn'>",
			"<head>",
			"  <meta charset='utf-8'>",
			"  <title>LLM4ArxivPaper 汇总</title>",
			"  <style>body{font-family:Segoe UI,Helvetica,Arial,sans-serif;margin:2rem;}" \
			"a{text-decoration:none;color:#0366d6;} .topic{margin-bottom:2rem;}" \
			"h1{margin-bottom:1rem;} ul{padding-left:1.2rem;}</style>",
			"</head>",
			"<body>",
			"  <h1>LLM4ArxivPaper 汇总</h1>",
		]

		if not index_entries:
			html_parts.append("  <p>暂未生成任何论文摘要。</p>")
		else:
			for topic_name, topic_summaries in index_entries:
				html_parts.append(f"  <div class='topic'>")
				html_parts.append(f"    <h2>{topic_summaries[0].topic.label} ({len(topic_summaries)})</h2>")
				html_parts.append("    <ul>")
				for summary in topic_summaries:
					relative_path = f"topics/{topic_name}/{summary.paper.arxiv_id}.html"
					url = f"{base_url}/{relative_path}" if base_url else relative_path
					html_parts.append(
						"      <li><a href='{url}'>{title}</a>".format(
							url=url,
							title=summary.paper.title,
						)
					)
				html_parts.append("    </ul>")
				html_parts.append("  </div>")

		html_parts.append("</body>")
		html_parts.append("</html>")
		return "\n".join(html_parts)

	def _render_paper(self, summary: PaperSummary) -> str:
		base_lines = [
			"<!DOCTYPE html>",
			"<html lang='zh-cn'>",
			"<head>",
			"  <meta charset='utf-8'>",
			f"  <title>{summary.paper.title}</title>",
			"  <style>body{font-family:Segoe UI,Helvetica,Arial,sans-serif;margin:2rem;}" \
			"h1{margin-bottom:0.5rem;} .meta{color:#555;margin-bottom:1.5rem;}" \
			"section{margin-bottom:1.5rem;} pre{white-space:pre-wrap;}</style>",
			"</head>",
			"<body>",
			f"  <a href='../..'>返回首页</a>",
			f"  <h1>{summary.paper.title}</h1>",
			"  <div class='meta'>",
			f"    <div>Topic: {summary.topic.label}</div>",
			f"    <div>Score: {self._format_score(summary.score_details)}</div>",
			f"    <div>Authors: {', '.join(summary.paper.authors)}</div>",
			f"    <div>arXiv: <a href='{summary.paper.arxiv_url}'>{summary.paper.arxiv_id}</a></div>",
			"  </div>",
			"  <section>",
			"    <h2>阅读 TODO</h2>",
			"    <ul>",
		]

		for task in summary.task_list:
			base_lines.append(f"      <li><strong>{task.question}</strong> – {task.reason}</li>")
		base_lines.extend([
			"    </ul>",
			"  </section>",
			"  <section>",
			"    <h2>逐项解答</h2>",
		])

		for finding in summary.findings:
			base_lines.append("    <article>")
			base_lines.append(f"      <h3>{finding.task.question}</h3>")
			base_lines.append(f"      <p>{finding.answer}</p>")
			base_lines.append(f"      <p><em>Confidence: {finding.confidence:.2f}</em></p>")
			base_lines.append("    </article>")

		base_lines.extend([
			"  </section>",
			"  <section>",
			"    <h2>综合总结</h2>",
			f"    <p>{summary.overview}</p>",
			"  </section>",
			"</body>",
			"</html>",
		])

		return "\n".join(base_lines)

	@staticmethod
	@staticmethod
	def _format_score(scored_paper) -> str:
		total_weight = sum(score.weight for score in scored_paper.scores) or 1.0
		value = sum(score.weight * score.value for score in scored_paper.scores)
		return f"{(value / total_weight) * 100:.1f}"
