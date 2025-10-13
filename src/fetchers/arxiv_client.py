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
			# arxiv.Client supports throttling parameters to control API call rate
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
		threshold_date = datetime.utcnow() - timedelta(days=self.fetch_config.days_back)
		
		# Prefer direct HTTPS request to avoid HTTP 301 redirect issue in arxiv library
		if requests is not None:
			print(f"[INFO] Fetching papers for topic '{topic.name}' via direct API...")
			papers = self._fallback_fetch(topic, threshold_date)
			if papers:
				return papers
			print(f"[WARN] Direct API fetch returned no results for topic '{topic.name}'")
		
		# Only fallback to arxiv.Client when requests is unavailable
		if self._client is None or arxiv is None:
			print("[WARN] Neither requests nor arxiv package available; returning empty results.")
			return []

		print(f"[INFO] Falling back to arxiv.Client for topic '{topic.name}'...")
		query = self._build_query(topic)
		search = arxiv.Search(
			query=query,
			max_results=self.fetch_config.max_papers_per_topic,
			sort_by=arxiv.SortCriterion.SubmittedDate,
			sort_order=arxiv.SortOrder.Descending,
		)

		papers: List[PaperCandidate] = []
		try:
			for result in self._client.results(search):
				published = result.published.replace(tzinfo=None) if result.published else None
				if published and published < threshold_date:
					continue

				arxiv_id = result.entry_id.split("/")[-1]
				if "v" in arxiv_id:
					arxiv_id = arxiv_id.split("v")[0]

				affiliations = []
				for author in result.authors:
					aff = getattr(author, "affiliation", None)
					if aff:
						aff_clean = aff.strip()
						if aff_clean and aff_clean not in affiliations:
							affiliations.append(aff_clean)

				comment = getattr(result, "comment", None)

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
					affiliations=affiliations,
					comment=comment,
				)

				papers.append(candidate)

				if len(papers) >= self.fetch_config.max_papers_per_topic:
					break

				sleep(self.fetch_config.request_delay)

		except Exception as exc:  # pragma: no cover
			print(f"[WARN] arxiv.Client also failed: {exc}")

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
		
		# Try HTTPS first (preferred), then HTTP if HTTPS fails
		urls = [
			"https://export.arxiv.org/api/query",
			"http://export.arxiv.org/api/query"
		]
		
		last_error = None
		for url in urls:
			try:
				print(f"[DEBUG] Attempting to fetch from: {url}")
				response = requests.get(url, params=params, timeout=30, allow_redirects=True)
				response.raise_for_status()
				
				# Successfully got a response, parse it
				print(f"[DEBUG] Successfully fetched from: {url}")
				result = self._parse_fallback_response(response.text, topic, threshold_date)
				
				# If we got results, return them
				if result:
					print(f"[DEBUG] Parsed {len(result)} papers from response")
					return result
				
				# If no results but valid response, check totalResults in XML
				if "totalResults" in response.text:
					# Valid response with 0 results is OK, return empty list
					print(f"[DEBUG] Valid response but 0 papers match the criteria")
					return []
				
				# Invalid response, try next URL
				print(f"[DEBUG] Invalid response from {url}, trying next URL...")
				continue
					
			except Exception as exc:
				last_error = exc
				print(f"[DEBUG] Failed to fetch from {url}: {exc}")
				continue
		
		# If we get here, all URLs failed
		print(f"[WARN] Fallback arXiv fetch failed with all URLs. Last error: {last_error}")
		return []

	def _parse_fallback_response(self, xml_text: str, topic: TopicConfig, threshold_date: datetime) -> List[PaperCandidate]:
		root = ET.fromstring(xml_text)
		ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
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
			affiliations: List[str] = []
			for author_el in entry.findall("atom:author", ns):
				aff_text = author_el.findtext("arxiv:affiliation", default="", namespaces=ns)
				if aff_text:
					aff_clean = aff_text.strip()
					if aff_clean and aff_clean not in affiliations:
						affiliations.append(aff_clean)
			categories = [cat.attrib.get("term", "") for cat in entry.findall("atom:category", ns) if cat.attrib.get("term")]
			
			# Parse arxiv:comment if present
			comment = entry.findtext("arxiv:comment", default=None, namespaces=ns)
			if comment:
				comment = comment.strip()

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
				affiliations=affiliations,
				comment=comment,
			)

			papers.append(candidate)

		return papers
