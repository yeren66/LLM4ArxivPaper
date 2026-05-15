"""ar5iv helper: Markdown text + key-figure extraction for arXiv papers."""

from __future__ import annotations

import re
from typing import Dict, List, Optional
from urllib.parse import urljoin

try:  # pragma: no cover - optional dependency warning suppression
	import html2text  # type: ignore[import]
except Exception:  # pragma: no cover
	html2text = None  # type: ignore[assignment]

try:  # pragma: no cover
	import requests  # type: ignore[import]
except Exception:
	requests = None  # type: ignore[assignment]

try:  # pragma: no cover
	from bs4 import BeautifulSoup  # type: ignore[import]
except Exception:  # pragma: no cover
	BeautifulSoup = None  # type: ignore[assignment]

from core.models import PaperFigure


# Caption keywords that signal a high-value "what is this paper" figure
# (the architecture / overview diagram). First figure also gets a boost.
_OVERVIEW_KEYWORDS = (
	"overview",
	"framework",
	"architecture",
	"pipeline",
	"workflow",
	"approach",
	"our method",
	"proposed method",
	"proposed framework",
	"system design",
	"illustration",
	"高层",
	"框架",
	"流程",
	"架构",
	"总览",
	"概览",
)
# Secondary keywords — results / comparison charts are useful but rank below
# the overview diagram.
_SECONDARY_KEYWORDS = (
	"result",
	"comparison",
	"ablation",
	"performance",
	"example",
	"case study",
	"实验",
	"对比",
	"消融",
	"示例",
)


class Ar5ivParser:
	"""Fetch ar5iv HTML once, then derive both a Markdown snippet and a
	short list of key figures from it."""

	def __init__(self, base_url: str = "https://ar5iv.org/html", timeout: int = 30):
		self.base_url = base_url.rstrip("/")
		self.timeout = timeout
		if html2text is not None:
			self._converter = html2text.HTML2Text()  # type: ignore[attr-defined]
			self._converter.ignore_links = False
			self._converter.body_width = 0
		else:  # pragma: no cover - fallback when dependency unavailable
			self._converter = None
		# Per-instance HTML cache so analyse() can call fetch_markdown +
		# fetch_figures without hitting the network twice.
		self._html_cache: Dict[str, Optional[str]] = {}

	# ------------------------------------------------------------------
	# raw HTML (cached)

	def _page_url(self, arxiv_id: str) -> str:
		return f"{self.base_url}/{arxiv_id}"

	def _fetch_html(self, arxiv_id: str) -> Optional[str]:
		if arxiv_id in self._html_cache:
			return self._html_cache[arxiv_id]
		if requests is None:
			print("[WARN] requests not installed; skipping ar5iv fetch.")
			self._html_cache[arxiv_id] = None
			return None
		try:
			response = requests.get(self._page_url(arxiv_id), timeout=self.timeout)
			response.raise_for_status()
			html = response.text
		except Exception as exc:  # pragma: no cover - network issues
			print(f"[WARN] Failed to fetch ar5iv content for {arxiv_id}: {exc}")
			html = None
		self._html_cache[arxiv_id] = html
		return html

	# ------------------------------------------------------------------
	# markdown

	def fetch_markdown(self, arxiv_id: str, max_chars: int = 12000) -> Optional[str]:
		"""Return a Markdown representation of a paper (trimmed to max_chars)."""
		if self._converter is None:
			print("[WARN] html2text not installed; skipping ar5iv markdown.")
			return None
		html = self._fetch_html(arxiv_id)
		if not html:
			return None
		markdown = self._converter.handle(html)
		markdown = self._clean(markdown)
		if max_chars and len(markdown) > max_chars:
			markdown = markdown[:max_chars] + "\n\n... (内容截断)"
		return markdown.strip()

	# ------------------------------------------------------------------
	# figures

	def fetch_method_figure(self, arxiv_id: str) -> Optional[PaperFigure]:
		"""Extract the single most informative figure — the method /
		architecture / flow diagram.

		Returns one :class:`PaperFigure` (or None). Selection is heuristic:
		the first figure is almost always the architecture overview in CS
		papers, and a caption mentioning framework/pipeline/architecture
		boosts the score. The figure's image URL is an absolute ar5iv link
		(hot-linked, no download). ``reference_text`` is populated with the
		body paragraphs that mention the figure — the paper's own words
		describing it, which the methodology prompt then leans on.
		"""
		if BeautifulSoup is None:  # pragma: no cover
			print("[WARN] beautifulsoup4 not installed; skipping figure extraction.")
			return None
		html = self._fetch_html(arxiv_id)
		if not html:
			return None

		try:
			soup = BeautifulSoup(html, "html.parser")
		except Exception as exc:  # pragma: no cover
			print(f"[WARN] Failed to parse ar5iv HTML for {arxiv_id}: {exc}")
			return None

		page_url = self._page_url(arxiv_id) + "/"
		raw: List[PaperFigure] = []
		# ar5iv (LaTeXML) renders figures as <figure class="ltx_figure">.
		figure_nodes = soup.find_all("figure", class_="ltx_figure") or soup.find_all("figure")
		for idx, fig in enumerate(figure_nodes):
			img = fig.find("img")
			if img is None or not img.get("src"):
				continue
			src = urljoin(page_url, img.get("src").strip())

			caption_node = fig.find("figcaption")
			caption = ""
			label = ""
			if caption_node is not None:
				# The "Figure N:" prefix lives in a <span class="ltx_tag_figure">.
				tag = caption_node.find("span", class_=re.compile(r"ltx_tag"))
				if tag is not None:
					label = tag.get_text(strip=True).rstrip(":：").strip()
				caption = caption_node.get_text(" ", strip=True)
			if not label:
				label = f"Figure {idx + 1}"

			raw.append(PaperFigure(label=label, caption=caption, url=src, order=idx))

		if not raw:
			return None

		best = max(raw, key=self._figure_score)
		best.reference_text = self._extract_reference_text(soup, best.label)
		return best

	@staticmethod
	def _extract_reference_text(soup, label: str) -> str:
		"""Collect body paragraphs that reference a given figure label.

		ar5iv numbers figures as "Figure 1", which the body cites as
		"Figure 1", "Fig. 1", "Fig 1" or (zh) "图 1". We grab up to three
		such paragraphs — the paper's own description of what the figure
		shows — and cap the total length so the prompt stays lean.
		"""
		m = re.search(r"(\d+)", label or "")
		if not m:
			return ""
		num = m.group(1)
		patterns = [
			re.compile(rf"\bfig(?:ure)?\.?\s*{num}\b", re.IGNORECASE),
			re.compile(rf"图\s*{num}\b"),
		]
		hits: List[str] = []
		for p in soup.find_all("p"):
			text = p.get_text(" ", strip=True)
			if not text or len(text) < 40:
				continue
			if any(pat.search(text) for pat in patterns):
				hits.append(text)
			if len(hits) >= 3:
				break
		joined = "\n\n".join(hits)
		return joined[:1500]

	@staticmethod
	def _figure_score(fig: PaperFigure) -> float:
		score = 0.0
		# The first figure is almost always the overview diagram.
		if fig.order == 0:
			score += 10.0
		caption_l = (fig.caption or "").lower()
		if any(k in caption_l for k in _OVERVIEW_KEYWORDS):
			score += 5.0
		if any(k in caption_l for k in _SECONDARY_KEYWORDS):
			score += 2.0
		# Mild penalty for figures with no caption at all (likely decorative).
		if not caption_l:
			score -= 1.0
		# Prefer earlier figures as a tie-breaker.
		score -= fig.order * 0.01
		return score

	# ------------------------------------------------------------------

	@staticmethod
	def _clean(markdown: str) -> str:
		# 移除重复空行，保持输出整洁
		markdown = re.sub(r"\n{3,}", "\n\n", markdown)
		return markdown
