"""ar5iv helper to obtain Markdown representation of arXiv papers."""

from __future__ import annotations

import re
from typing import Optional

try:  # pragma: no cover - optional dependency warning suppression
	import html2text  # type: ignore[import]
except Exception:  # pragma: no cover
	html2text = None  # type: ignore[assignment]

try:  # pragma: no cover
	import requests  # type: ignore[import]
except Exception:
	requests = None  # type: ignore[assignment]


class Ar5ivParser:
	"""Fetch and convert ar5iv HTML pages to Markdown snippets."""

	def __init__(self, base_url: str = "https://ar5iv.org/html", timeout: int = 30):
		self.base_url = base_url.rstrip("/")
		self.timeout = timeout
		if html2text is not None:
			self._converter = html2text.HTML2Text()  # type: ignore[attr-defined]
			self._converter.ignore_links = False
			self._converter.body_width = 0
		else:  # pragma: no cover - fallback when dependency unavailable
			self._converter = None

	def fetch_markdown(self, arxiv_id: str, max_chars: int = 12000) -> Optional[str]:
		"""Return markdown representation of a paper.

		Args:
			arxiv_id: Canonical arXiv identifier (without version suffix).
			max_chars: Trim output to avoid overly long prompts.
		"""

		url = f"{self.base_url}/{arxiv_id}"
		if requests is None or self._converter is None:
			print("[WARN] html2text/requests not installed; skipping ar5iv fetch.")
			return None

		try:
			response = requests.get(url, timeout=self.timeout)
			response.raise_for_status()
		except Exception as exc:  # pragma: no cover - network issues
			print(f"[WARN] Failed to fetch ar5iv content for {arxiv_id}: {exc}")
			return None

		markdown = self._converter.handle(response.text)
		markdown = self._clean(markdown)
		if max_chars and len(markdown) > max_chars:
			markdown = markdown[:max_chars] + "\n\n... (内容截断)"
		return markdown.strip()

	@staticmethod
	def _clean(markdown: str) -> str:
		# 移除重复空行，保持输出整洁
		markdown = re.sub(r"\n{3,}", "\n\n", markdown)
		return markdown
