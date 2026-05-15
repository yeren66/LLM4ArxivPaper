"""Utilities for querying arXiv."""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from time import monotonic, sleep
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

from core.models import FetchConfig, PaperCandidate, TopicConfig, TopicQuery


# arXiv asks API clients to identify themselves; an unidentified client gets
# rate-limited much more aggressively. See https://info.arxiv.org/help/api/.
_ARXIV_USER_AGENT = "LLM4ArxivPaper/2.0 (weekly arXiv digest bot; +https://github.com/yeren66/LLM4ArxivPaper)"

# arXiv's published guidance: no more than one request every ~3 seconds.
_MIN_REQUEST_INTERVAL = 3.0

# How many times to retry a request that comes back 429/503 before giving up.
# Six attempts with capped exponential backoff (3s, 6s, 12s, 24s, 48s, 60s
# with jitter) totals ~150s worst-case — enough to ride out a typical arXiv
# rate-limit spell without ballooning into multi-minute waits per request.
_MAX_RETRIES = 6
_MAX_BACKOFF = 60.0

# When a request gives up after exhausting retries, the client enters a
# process-wide cooldown so the *next* call (e.g. the next topic) doesn't
# immediately re-trigger the same arXiv-side rate limit. Empirically GitHub
# Actions runs hit topics back-to-back and the second one always failed
# unless the client first paused.
_COOLDOWN_AFTER_GIVEUP = 60.0

# Cap on what we honour from a server-supplied `Retry-After` — arXiv has
# been seen returning unreasonable values on occasion.
_MAX_RETRY_AFTER = 120.0

# (connect, read) tuple. arXiv stays slow when overloaded; a generous read
# timeout keeps us from mis-counting slow-but-eventual responses as timeouts.
_REQUEST_TIMEOUT = (15, 60)

_ARXIV_API_URL = "https://export.arxiv.org/api/query"


class ArxivClient:
	"""Thin wrapper around the :mod:`arxiv` package.

	The class focuses on building expressive queries from topic configuration
	and converting results into :class:`PaperCandidate` objects.
	"""

	def __init__(self, fetch_config: FetchConfig):
		self.fetch_config = fetch_config
		# Wall-clock time of the most recent arXiv API request. Used by
		# :meth:`_throttle` to keep the *whole process* under arXiv's rate
		# limit — across pagination AND across topics, not just within one
		# pagination loop.
		self._last_request_at: float = 0.0
		# Earliest monotonic time at which the next request is allowed to go
		# out. Bumped whenever a request gives up after exhausting retries,
		# so a following topic doesn't immediately re-trigger the rate limit.
		self._cooldown_until: float = 0.0
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

	def _build_query(
		self,
		topic: TopicConfig,
		start_date: Optional[datetime] = None,
		end_date: Optional[datetime] = None,
	) -> str:
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

		# Server-side date range filter — only used when an explicit window is
		# provided (e.g. by the backfill workflow); the weekly run still relies
		# on client-side `threshold_date` filtering via `days_back`.
		if start_date and end_date:
			s = start_date.strftime("%Y%m%d%H%M")
			e = end_date.strftime("%Y%m%d%H%M")
			parts.append(f"submittedDate:[{s} TO {e}]")

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
	# HTTP layer: one throttled, retrying entry point for every arXiv API
	# call. Both the paginated topic fetch and the single-id fetch go through
	# :meth:`_arxiv_get`, so rate-limit handling lives in exactly one place.
	# ------------------------------------------------------------------

	def _throttle(self) -> None:
		"""Block until the next request is allowed.

		Enforces two constraints:
		1. The minimum gap between requests (the larger of arXiv's published
		   3-second guidance and the configured ``request_delay``), across
		   pagination AND across topics within one pipeline run.
		2. The post-give-up cooldown, so a freshly-failed request's rate
		   limit doesn't bleed into the next topic.
		"""
		interval = max(_MIN_REQUEST_INTERVAL, self.fetch_config.request_delay)
		now = monotonic()
		ready_at = max(self._last_request_at + interval, self._cooldown_until)
		if ready_at > now:
			wait = ready_at - now
			# Don't spam the log for the routine sub-second throttle; do flag
			# the longer waits so the run log shows the cooldown kicking in.
			if wait >= 5.0:
				print(f"[INFO] pausing {wait:.0f}s before next arXiv request (cooldown)")
			sleep(wait)
		self._last_request_at = monotonic()

	def _backoff_seconds(self, attempt: int) -> float:
		"""Exponential backoff with a cap and ±15 % jitter.

		Jitter matters in CI: multiple GitHub Actions jobs hitting arXiv at
		the same time would otherwise retry in lockstep and dogpile the
		server. Spreading them out gives a much better chance of one of
		them landing on a moment arXiv is willing to answer.
		"""
		base = max(_MIN_REQUEST_INTERVAL, self.fetch_config.request_delay)
		raw = base * (2 ** (attempt - 1))
		capped = min(_MAX_BACKOFF, raw)
		return capped * random.uniform(0.85, 1.15)

	def _enter_cooldown(self, reason: str) -> None:
		"""Push the next-allowed-request time out by the cooldown window."""
		self._cooldown_until = monotonic() + _COOLDOWN_AFTER_GIVEUP
		print(
			f"[INFO] arXiv client entering {_COOLDOWN_AFTER_GIVEUP:.0f}s "
			f"cooldown ({reason})"
		)

	def _arxiv_get(self, params: dict) -> Optional[str]:
		"""GET the arXiv API once, with throttling, a descriptive User-Agent,
		retry-with-exponential-backoff on 429/503 / network errors, and a
		process-wide cooldown when retries are exhausted.

		Returns the response body, or ``None`` if every attempt failed (the
		caller treats that as "no results" and carries on).
		"""
		if requests is None:
			print("[WARN] requests library unavailable; cannot call arXiv API.")
			return None

		headers = {"User-Agent": _ARXIV_USER_AGENT}

		for attempt in range(1, _MAX_RETRIES + 1):
			# Always wait out the polite interval (and any active cooldown)
			# before sending — including before the very first request.
			self._throttle()
			try:
				response = requests.get(
					_ARXIV_API_URL,
					params=params,
					headers=headers,
					timeout=_REQUEST_TIMEOUT,
				)
			except Exception as exc:
				print(
					f"[WARN] arXiv API request errored (attempt {attempt}/{_MAX_RETRIES}): {exc}"
				)
				if attempt < _MAX_RETRIES:
					wait = self._backoff_seconds(attempt)
					print(f"[INFO] retrying in {wait:.0f}s ...")
					sleep(wait)
					continue
				self._enter_cooldown("network errors persisted")
				return None

			# 429 = rate limited, 503 = arXiv asking us to back off. Both are
			# transient: honour Retry-After if given (capped), else jittered
			# exponential backoff.
			if response.status_code in (429, 503):
				retry_after = response.headers.get("Retry-After", "").strip()
				if retry_after.isdigit():
					wait = min(_MAX_RETRY_AFTER, float(retry_after))
				else:
					wait = self._backoff_seconds(attempt)
				print(
					f"[WARN] arXiv API returned {response.status_code} "
					f"(attempt {attempt}/{_MAX_RETRIES})"
				)
				if attempt < _MAX_RETRIES:
					print(f"[INFO] backing off {wait:.0f}s before retry ...")
					sleep(wait)
					continue
				print("[WARN] arXiv API rate limit persisted; giving up on this request.")
				self._enter_cooldown("rate limit persisted")
				return None

			try:
				response.raise_for_status()
			except Exception as exc:
				print(f"[WARN] arXiv API HTTP error: {exc}")
				return None

			return response.text

		return None

	# ------------------------------------------------------------------

	def fetch_for_topic(
		self,
		topic: TopicConfig,
		start_date: Optional[datetime] = None,
		end_date: Optional[datetime] = None,
		max_results: Optional[int] = None,
	) -> List[PaperCandidate]:
		"""Fetch papers for a topic.

		When ``start_date``/``end_date`` are provided the date filter is pushed
		into the arXiv server query and pagination kicks in to walk the full
		window. Otherwise the legacy "last N days" behaviour is used.
		"""

		threshold_date = (
			start_date if start_date is not None
			else datetime.utcnow() - timedelta(days=self.fetch_config.days_back)
		)
		cap = max_results if max_results is not None else self.fetch_config.max_papers_per_topic

		if requests is not None:
			print(f"[INFO] Fetching papers for topic '{topic.name}' via direct API...")
			return self._fallback_fetch(
				topic, threshold_date, start_date=start_date, end_date=end_date, max_results=cap
			)

		# Only fallback to arxiv.Client when requests is unavailable
		if self._client is None or arxiv is None:
			print("[WARN] Neither requests nor arxiv package available; returning empty results.")
			return []

		print(f"[INFO] Falling back to arxiv.Client for topic '{topic.name}'...")
		query = self._build_query(topic, start_date=start_date, end_date=end_date)
		search = arxiv.Search(
			query=query,
			max_results=cap,
			sort_by=arxiv.SortCriterion.SubmittedDate,
			sort_order=arxiv.SortOrder.Descending,
		)

		papers: List[PaperCandidate] = []
		try:
			for result in self._client.results(search):
				published = result.published.replace(tzinfo=None) if result.published else None
				# Skip out-of-window papers. When an explicit window is given the
				# server should already enforce it, but stale results can slip
				# through for ~minute-old papers; double-check client-side.
				if published and published < threshold_date:
					continue
				if end_date and published and published > end_date:
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

				if len(papers) >= cap:
					break

				sleep(self.fetch_config.request_delay)

		except Exception as exc:  # pragma: no cover
			print(f"[WARN] arxiv.Client also failed: {exc}")

		return papers

	def fetch_one(
		self, arxiv_id: str, topic: Optional[TopicConfig] = None
	) -> Optional[PaperCandidate]:
		"""Fetch metadata for a single arXiv ID via the API ``id_list`` query.

		Unlike :meth:`fetch_for_topic` this bypasses keyword/category/date
		filtering — useful when the user manually submits a paper URL.
		"""

		if requests is None:
			print("[WARN] requests unavailable; cannot fetch single arXiv id.")
			return None

		# Canonicalise: strip optional version suffix (2401.12345v2 -> 2401.12345)
		clean_id = arxiv_id.strip()
		if "v" in clean_id and clean_id.rsplit("v", 1)[-1].isdigit():
			clean_id = clean_id.rsplit("v", 1)[0]

		if topic is None:
			topic = TopicConfig(
				name="ad-hoc",
				label="Ad-hoc submission",
				query=TopicQuery(),
				interest_prompt="",
			)

		params = {"id_list": clean_id, "max_results": 1}
		xml_text = self._arxiv_get(params)
		if xml_text is None:
			print(f"[WARN] fetch_one failed for {clean_id} (arXiv API unavailable or rate limited).")
			return None

		# Reuse the Atom parser but with no date filter.
		candidates = self._parse_fallback_response(
			xml_text, topic, datetime.min, end_date=None
		)
		return candidates[0] if candidates else None

	def _fallback_fetch(
		self,
		topic: TopicConfig,
		threshold_date: datetime,
		start_date: Optional[datetime] = None,
		end_date: Optional[datetime] = None,
		max_results: Optional[int] = None,
	) -> List[PaperCandidate]:
		if requests is None:
			print("[WARN] requests library unavailable; cannot perform fallback fetch.")
			return []

		cap = max_results if max_results is not None else self.fetch_config.max_papers_per_topic
		query = self._build_query(topic, start_date=start_date, end_date=end_date)
		# arXiv enforces a soft cap of ~2000 per page; 100 is friendly to the
		# `Retry-After`-style rate limit and easy to debug.
		page_size = min(100, cap)
		collected: List[PaperCandidate] = []
		offset = 0

		while len(collected) < cap:
			batch_size = min(page_size, cap - len(collected))
			params = {
				"search_query": query,
				"sortBy": "submittedDate",
				"sortOrder": "descending",
				"start": offset,
				"max_results": batch_size,
			}
			# Throttling, User-Agent and 429/503 retry all live in _arxiv_get.
			xml_text = self._arxiv_get(params)
			if xml_text is None:
				print(f"[WARN] arXiv fetch failed at offset {offset}; stopping pagination for this topic.")
				break

			page = self._parse_fallback_response(
				xml_text, topic, threshold_date, end_date=end_date
			)
			if not page:
				break
			collected.extend(page)
			offset += batch_size

		return collected[:cap]

	def _parse_fallback_response(
		self,
		xml_text: str,
		topic: TopicConfig,
		threshold_date: datetime,
		end_date: Optional[datetime] = None,
	) -> List[PaperCandidate]:
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
			if end_date is not None and published_dt > end_date:
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
