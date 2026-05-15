"""Extract the method/architecture figure straight from a paper's PDF.

Why this exists: ar5iv renders arXiv papers from LaTeX source and lags the
arXiv listing by days to weeks, so for *freshly published* papers — exactly
what this tool targets — ar5iv usually has nothing. The PDF, on the other
hand, is available the moment a paper is posted.

Approach: find "Figure N" caption blocks in the PDF text, locate the actual
drawn/embedded content sitting above the chosen caption (vector drawings +
raster images + in-figure text labels, bounded above by the nearest body
paragraph), render *that region*, and return it as a WebP ``data:`` URI.
Rendering a region rather than pulling embedded images is deliberate: most
CS architecture diagrams are vector (TikZ), so there is no embedded raster
to pull — but a region render captures vector and raster alike.

WebP keeps the encoded figure ~3x smaller than PNG; the data URI travels
inside the analysis JSON like every other field, so no image hosting or
extra serving route is needed.
"""

from __future__ import annotations

import base64
import io
import re
import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

try:  # pragma: no cover - optional dependency
	import fitz  # PyMuPDF
except Exception:  # pragma: no cover
	fitz = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency
	from PIL import Image  # type: ignore[import]
except Exception:  # pragma: no cover
	Image = None  # type: ignore[assignment]

try:  # pragma: no cover
	import requests  # type: ignore[import]
except Exception:  # pragma: no cover
	requests = None  # type: ignore[assignment]

from core.models import PaperFigure
from fetchers.ar5iv_parser import Ar5ivParser


# A caption block starts with "Figure 3", "Fig. 3", "Fig 3" or (zh) "图 3".
# Anchored at the start of the block so body sentences like "see Figure 3"
# do not match.
_CAPTION_RE = re.compile(r"^\s*(?:figure|fig\.?|图)\s*(\d+)\b[\s:.：、,]*", re.IGNORECASE)

# Method figures live near the front of a paper; don't scan the whole thing.
_MAX_PAGES_TO_SCAN = 14


class PDFFigureExtractor:
	"""Pull the single best method figure out of a paper PDF."""

	def __init__(
		self,
		timeout: int = 30,
		render_dpi: int = 150,
		max_px: int = 1100,
		webp_quality: int = 80,
	):
		self.timeout = timeout
		self.render_dpi = render_dpi
		# Hard cap on the rendered figure's longest side, to keep the data URI
		# (and therefore the analysis JSON) from ballooning.
		self.max_px = max_px
		# WebP encode quality. WebP at ~80 keeps method figures crisp while
		# coming in roughly a third the size of the equivalent PNG.
		self.webp_quality = webp_quality

	# ------------------------------------------------------------------

	def fetch(self, pdf_url: str, arxiv_id: str = "") -> Optional[PaperFigure]:
		"""Download ``pdf_url`` and return its method figure, or None.

		Best-effort: any failure (PyMuPDF missing, download timeout, no
		captions found) just yields None and the caller carries on
		figure-less.
		"""
		if fitz is None:
			print("[WARN] PyMuPDF (fitz) not installed; skipping PDF figure extraction.")
			return None
		if requests is None:
			print("[WARN] requests not installed; skipping PDF figure extraction.")
			return None
		if not pdf_url:
			return None

		tmp_path: Optional[str] = None
		try:
			resp = requests.get(pdf_url, timeout=self.timeout)
			resp.raise_for_status()
			with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as fh:
				fh.write(resp.content)
				tmp_path = fh.name
			return self._extract(tmp_path)
		except Exception as exc:  # pragma: no cover - network / parse issues
			print(f"[WARN] PDF figure extraction failed for {arxiv_id or pdf_url}: {exc}")
			return None
		finally:
			if tmp_path:
				Path(tmp_path).unlink(missing_ok=True)

	# ------------------------------------------------------------------

	def _extract(self, pdf_path: str) -> Optional[PaperFigure]:
		doc = fitz.open(pdf_path)
		try:
			# Pass 1: collect every caption block and every text block (the
			# latter doubles as the paragraph corpus for reference_text).
			captions: List[Tuple[int, "fitz.Rect", int, str]] = []  # (page_idx, bbox, num, caption_text)
			block_texts: List[str] = []
			n_pages = min(doc.page_count, _MAX_PAGES_TO_SCAN)
			for pidx in range(n_pages):
				page = doc[pidx]
				for block in page.get_text("blocks"):
					x0, y0, x1, y1, text = block[0], block[1], block[2], block[3], block[4]
					text = (text or "").strip()
					if not text:
						continue
					block_texts.append(text)
					m = _CAPTION_RE.match(text)
					if m:
						captions.append((pidx, fitz.Rect(x0, y0, x1, y1), int(m.group(1)), text))

			if not captions:
				return None

			# Order figures by appearance (page, then vertical position) so the
			# shared scorer's "first figure is usually the overview" boost lands
			# on the right one.
			captions.sort(key=lambda c: (c[0], c[1].y0))

			# Pass 2: score each caption with the SAME heuristic ar5iv uses, so
			# PDF-sourced and ar5iv-sourced figures are picked consistently.
			best_idx = 0
			best_score = float("-inf")
			for order, (pidx, cbbox, num, ctext) in enumerate(captions):
				caption_clean = _CAPTION_RE.sub("", ctext, count=1).strip()
				stub = PaperFigure(label=f"Figure {num}", caption=caption_clean, url="", order=order)
				s = Ar5ivParser._figure_score(stub)
				if s > best_score:
					best_score, best_idx = s, order

			order = best_idx
			pidx, cbbox, num, ctext = captions[order]
			caption_clean = _CAPTION_RE.sub("", ctext, count=1).strip()

			page = doc[pidx]
			region = self._figure_region(page, cbbox)
			if region is None:
				return None

			data_uri = self._render_region(page, region)
			if not data_uri:
				return None

			reference_text = self._reference_text(block_texts, num)

			return PaperFigure(
				label=f"Figure {num}",
				caption=caption_clean,
				url=data_uri,
				order=order,
				reference_text=reference_text,
			)
		finally:
			doc.close()

	# ------------------------------------------------------------------

	def _figure_region(self, page, caption_bbox) -> Optional["fitz.Rect"]:
		"""Find the rectangle the figure actually occupies, just above its
		caption.

		The figure's real extent is defined by its DRAWINGS and IMAGES — body
		prose has neither — so those anchor the region. Text blocks are folded
		in afterwards, but only when they fall inside the drawn extent, so
		prose from outside the figure can never inflate the box. We do not try
		to guess columns from the caption (a short centred caption was getting
		misread as a narrow column and clipping wide figures); letting the
		drawn content define the width handles one- and two-column layouts
		alike.
		"""
		pw, ph = page.rect.width, page.rect.height
		blocks = page.get_text("blocks")

		# Search band: above the caption, but never reaching into the running
		# -header zone at the very top of the page (page numbers, author names
		# and the paper title live there and used to leak in).
		band_top = max(caption_bbox.y0 - ph * 0.80, ph * 0.09)
		band = fitz.Rect(0.0, band_top, pw, caption_bbox.y0)
		if band.height < 24.0:
			return None

		core: List["fitz.Rect"] = []
		page_area = pw * ph

		# Body paragraphs on this page. Used to recognise (and reject) layout
		# boxes: a rectangle that *wraps a body paragraph* is a border around
		# the abstract / a section panel, not figure content.
		body_rects = [
			fitz.Rect(b[0], b[1], b[2], b[3])
			for b in blocks
			if len((b[4] or "").strip()) > 200
		]

		# Vector drawings (TikZ diagrams, arrows, boxes...).
		for d in page.get_drawings():
			r = fitz.Rect(d["rect"])
			if r.is_empty or r.is_infinite:
				continue
			# Ignore hairline rules — underlines, column separators, table
			# rules, box borders: thin in one dimension, long in the other.
			if (r.height < 3.0 and r.width > pw * 0.25) or (
				r.width < 3.0 and r.height > ph * 0.15
			):
				continue
			# Ignore page-sized tints / backgrounds.
			if abs(r.width * r.height) > page_area * 0.30:
				continue
			# Ignore layout boxes: a rectangle that wraps a body paragraph.
			if any(self._contained_frac(br, r) > 0.5 for br in body_rects):
				continue
			if self._contained_frac(r, band) > 0.5:
				core.append(r & band)

		# Embedded raster images.
		try:
			image_infos = page.get_image_info()
		except Exception:  # pragma: no cover - older PyMuPDF
			image_infos = []
		for info in image_infos:
			r = fitz.Rect(info["bbox"])
			if self._contained_frac(r, band) > 0.5:
				core.append(r & band)

		if not core:
			return None

		# Group the boxes into spatially-connected clusters and keep the one
		# that lines up horizontally with the caption. A figure's caption sits
		# within the figure's horizontal span, so this drops content from
		# another column — or a different figure — that merely happens to
		# share the vertical band. The gap is deliberately small: a figure's
		# own pieces are bridged by its drawn arrows/lines (which are in
		# ``core``), so they stay connected without a generous gap, while a
		# separate column stays separate.
		clusters = self._cluster(core, gap=pw * 0.022)

		def _caption_overlap(rect) -> float:
			left = max(rect.x0, caption_bbox.x0)
			right = min(rect.x1, caption_bbox.x1)
			return max(0.0, right - left)

		region = max(clusters, key=_caption_overlap)
		if _caption_overlap(region) <= 0.0:
			# Nothing lines up with the caption — fall back to the biggest
			# cluster rather than dropping the figure entirely.
			region = max(clusters, key=lambda r: abs(r.width * r.height))

		# Fold in text labels that fall within the drawn extent (node labels,
		# axis ticks, legends). Constrained to this zone, text refines the box
		# but can never inflate it with prose from outside the figure.
		label_zone = fitz.Rect(
			region.x0 - pw * 0.04,
			region.y0 - 6.0,
			region.x1 + pw * 0.04,
			caption_bbox.y0,
		)
		for b in blocks:
			r = fitz.Rect(b[0], b[1], b[2], b[3])
			if r.intersects(caption_bbox):
				continue
			# Figure labels are short; never fold a body paragraph in.
			if len((b[4] or "").strip()) > 200:
				continue
			if self._contained_frac(r, label_zone) > 0.65:
				region |= (r & band)

		region &= band

		# Small pad; never let the bottom edge cross into the caption.
		region = fitz.Rect(
			region.x0 - 3.0,
			region.y0 - 3.0,
			region.x1 + 3.0,
			min(caption_bbox.y0 - 1.0, region.y1 + 3.0),
		)
		if region.width < 40.0 or region.height < 30.0:
			return None
		return region

	# ------------------------------------------------------------------

	def _render_region(self, page, region) -> Optional[str]:
		"""Render ``region`` of ``page`` and return it as a WebP data: URI.

		WebP is ~3x smaller than the equivalent PNG, which matters because the
		encoded image lives inside the analysis JSON. Falls back to PNG if
		Pillow is not installed.
		"""
		zoom = self.render_dpi / 72.0
		try:
			pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=region, alpha=False)
		except Exception as exc:  # pragma: no cover
			print(f"[WARN] figure region render failed: {exc}")
			return None
		if pix.width == 0 or pix.height == 0:
			return None

		if Image is None:  # pragma: no cover - Pillow not installed
			png = pix.tobytes("png")
			if not png:
				return None
			return "data:image/png;base64," + base64.b64encode(png).decode("ascii")

		try:
			# Go through PNG bytes so PIL handles the colourspace/stride; the
			# intermediate encode is cheap for a figure-sized image.
			img = Image.open(io.BytesIO(pix.tobytes("png")))
			longest = max(img.width, img.height)
			if longest > self.max_px:
				scale = self.max_px / longest
				img = img.resize(
					(max(1, round(img.width * scale)), max(1, round(img.height * scale))),
					Image.LANCZOS,
				)
			buf = io.BytesIO()
			img.convert("RGB").save(buf, "WEBP", quality=self.webp_quality, method=6)
			data = buf.getvalue()
		except Exception as exc:  # pragma: no cover
			print(f"[WARN] figure WebP encode failed: {exc}")
			return None
		if not data:
			return None
		return "data:image/webp;base64," + base64.b64encode(data).decode("ascii")

	# ------------------------------------------------------------------

	@staticmethod
	def _reference_text(block_texts: List[str], num: int) -> str:
		"""Body paragraphs that mention "Figure N" — the paper's own words
		describing the figure. Mirrors Ar5ivParser._extract_reference_text."""
		patterns = [
			re.compile(rf"\bfig(?:ure)?\.?\s*{num}\b", re.IGNORECASE),
			re.compile(rf"图\s*{num}\b"),
		]
		hits: List[str] = []
		for text in block_texts:
			flat = re.sub(r"\s+", " ", text).strip()
			if len(flat) < 40:
				continue
			# Skip the caption block itself.
			if _CAPTION_RE.match(flat):
				continue
			if any(p.search(flat) for p in patterns):
				hits.append(flat)
			if len(hits) >= 3:
				break
		return "\n\n".join(hits)[:1500]

	@staticmethod
	def _cluster(boxes: List["fitz.Rect"], gap: float) -> List["fitz.Rect"]:
		"""Merge boxes into spatially-connected clusters.

		Two boxes join the same cluster if their bounding rects come within
		``gap`` of each other — figure elements (nodes, arrows, labels) sit
		close together, while a separate figure or another text column is
		divided by a clear margin. Returns one bounding rect per cluster.
		"""
		clusters = [fitz.Rect(b) for b in boxes]
		merged = True
		while merged:
			merged = False
			out: List["fitz.Rect"] = []
			for c in clusters:
				inflated = fitz.Rect(c.x0 - gap, c.y0 - gap, c.x1 + gap, c.y1 + gap)
				for i, existing in enumerate(out):
					if inflated.intersects(existing):
						out[i] = existing | c
						merged = True
						break
				else:
					out.append(fitz.Rect(c))
			clusters = out
		return clusters

	@staticmethod
	def _contained_frac(r, band) -> float:
		"""Fraction of rectangle ``r``'s area that lies inside ``band``."""
		area = abs(r.width * r.height)
		if area <= 0:
			return 0.0
		inter = r & band
		if inter.is_empty:
			return 0.0
		return abs(inter.width * inter.height) / area
