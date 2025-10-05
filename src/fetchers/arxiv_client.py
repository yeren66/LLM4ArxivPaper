"""Utilities for querying arXiv."""

from __future__ import annotations

from datetime import datetime, timedelta
from time import sleep
from typing import List, Optional

from dateutil import parser as date_parser
from xml.etree import ElementTree as ET

try:  # pragma: no cover - optional dependency during linting
	import arxiv  # type: ignore[import]
except Exception:  # pragma: no cover - keep going even if arxiv missing
	arxiv = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency in CI
	import requests  # type: ignore[import]
except Exception:  # pragma: no cover
	requests = None  # type: ignore[assignment]

from core.models import FetchConfig, PaperCandidate, TopicConfig


class ArxivClient:
	"""Thin wrapper around the :mod:`arxiv` package.

	The class focuses on building expressive queries from topic configuration
	and converting results into :class:`PaperCandidate` objects.
	"""

	def __init__(self, fetch_config: FetchConfig):
		self.fetch_config = fetch_config
		if arxiv is not None:
			# arxiv.Client 支持节流参数，用于控制 API 调用速率
			self._client: Optional[arxiv.Client] = arxiv.Client(  # type: ignore[attr-defined]
				page_size=100,
				delay_seconds=fetch_config.request_delay,
			)
		else:  # pragma: no cover - fallback when dependency unavailable
			self._client = None

	# ------------------------------------------------------------------
	# Query helpers
	# ------------------------------------------------------------------

	def _build_query(self, topic: TopicConfig) -> str:
		parts: List[str] = []

		if topic.query.include:
			include_expr = [self._keyword_clause(keyword) for keyword in topic.query.include]
			parts.append(f"({' OR '.join(include_expr)})")

		if topic.query.categories:
			cat_expr = [f"cat:{cat}" for cat in topic.query.categories]
			parts.append(f"({' OR '.join(cat_expr)})")

		if topic.query.exclude:
			exclude_expr = [self._keyword_clause(keyword) for keyword in topic.query.exclude]
			parts.append(f"NOT ({' OR '.join(exclude_expr)})")

		if not parts:
			return "all:cs"

		return " AND ".join(parts)

	@staticmethod
	def _keyword_clause(keyword: str) -> str:
		keyword = keyword.strip()
		if " " in keyword:
			return f'ti:"{keyword}" OR abs:"{keyword}"'
		return f'ti:{keyword} OR abs:{keyword}'

	# ------------------------------------------------------------------

	def fetch_for_topic(self, topic: TopicConfig) -> List[PaperCandidate]:
		if self._client is None or arxiv is None:
			print("[WARN] arxiv package not available; returning empty results.")
			return []

		query = self._build_query(topic)
		search = arxiv.Search(
			query=query,
			max_results=self.fetch_config.max_papers_per_topic,
			sort_by=arxiv.SortCriterion.SubmittedDate,
			sort_order=arxiv.SortOrder.Descending,
		)

		threshold_date = datetime.utcnow() - timedelta(days=self.fetch_config.days_back)
		papers: List[PaperCandidate] = []

		try:
			for result in self._client.results(search):
				published = result.published.replace(tzinfo=None) if result.published else None
				if published and published < threshold_date:
					continue

				arxiv_id = result.entry_id.split("/")[-1]
				if "v" in arxiv_id:
					arxiv_id = arxiv_id.split("v")[0]

				candidate = PaperCandidate(
					topic=topic,
					arxiv_id=arxiv_id,
					title=result.title.strip(),
					abstract=result.summary.strip(),
					authors=[author.name for author in result.authors],
					categories=list(result.categories),
					published=published or datetime.utcnow(),
					updated=(result.updated.replace(tzinfo=None) if result.updated else datetime.utcnow()),
					arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
					pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
				)

				papers.append(candidate)

				if len(papers) >= self.fetch_config.max_papers_per_topic:
					break

				# 异步客户端已经支持 delay_seconds，但这里仍然显式 sleep，确保兼容
				sleep(self.fetch_config.request_delay)

		except Exception as exc:  # pragma: no cover - 网络相关错误直接暴露即可
			print(f"[WARN] Failed to fetch arXiv results for topic '{topic.name}': {exc}")
			return self._fallback_fetch(topic, threshold_date)

		return papers

	def _fallback_fetch(self, topic: TopicConfig, threshold_date: datetime) -> List[PaperCandidate]:
		if requests is None:
			print("[WARN] requests library unavailable; cannot perform fallback fetch.")
			return []

		query = self._build_query(topic)
		params = {
			"search_query": query,
			"sortBy": "submittedDate",
			"sortOrder": "descending",
			"start": 0,
			"max_results": self.fetch_config.max_papers_per_topic,
		}
		url = "https://export.arxiv.org/api/query"
		try:
			response = requests.get(
				url,
				params=params,
				timeout=30,
				headers={"User-Agent": "LLM4ArxivPaper/1.0 (fallback)"},
			)
			response.raise_for_status()
		except Exception as exc:  # pragma: no cover
			print(f"[WARN] Fallback arXiv fetch failed: {exc}")
			return []

		try:
			root = ET.fromstring(response.text)
		except ET.ParseError as exc:  # pragma: no cover
			print(f"[WARN] Unable to parse arXiv response: {exc}")
			return []

		ns = {"atom": "http://www.w3.org/2005/Atom"}
		papers: List[PaperCandidate] = []

		for entry in root.findall("atom:entry", ns):
			id_element = entry.find("atom:id", ns)
			if id_element is None or not id_element.text:
				continue
			arxiv_id = id_element.text.split("/")[-1]
			if "v" in arxiv_id:
				arxiv_id = arxiv_id.split("v")[0]

			title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
			summary = (entry.findtext("atom:summary", default="", namespaces=ns) or "").strip()

			published_text = entry.findtext("atom:published", default="", namespaces=ns)
			updated_text = entry.findtext("atom:updated", default=published_text, namespaces=ns)

			try:
				published_dt = date_parser.isoparse(published_text).replace(tzinfo=None)
			except Exception:
				published_dt = datetime.utcnow()

			if published_dt < threshold_date:
				continue

			try:
				updated_dt = date_parser.isoparse(updated_text).replace(tzinfo=None)
			except Exception:
				updated_dt = published_dt

			authors = [author.text for author in entry.findall("atom:author/atom:name", ns) if author.text]
			categories = [cat.attrib.get("term", "") for cat in entry.findall("atom:category", ns) if cat.attrib.get("term")]

			candidate = PaperCandidate(
				topic=topic,
				arxiv_id=arxiv_id,
				title=title,
				abstract=summary,
				authors=authors or ["Unknown"],
				categories=categories,
				published=published_dt,
				updated=updated_dt,
				arxiv_url=f"https://arxiv.org/abs/{arxiv_id}",
				pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
			)

			papers.append(candidate)

		return papers
