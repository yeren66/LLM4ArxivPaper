"""File-based persistence: write analyses to ``data/`` as plain JSON files
so the git repo itself is the database.

Design:
- ``data/analyses/{arxiv_id}.json`` — one file per paper, the full payload
  produced by :func:`workflow.pipeline._summary_to_payload`.
- ``data/index.json`` — a slim list of every analysis (arxiv_id, topic,
  score, title, authors, published, generated_at) ordered newest-first.
  Vercel reads this for the home page listing; we maintain it incrementally
  so the home page never has to scan the whole ``analyses/`` directory.

Writes happen on the **local filesystem** of whichever process runs the
pipeline. The corresponding GitHub Actions workflow then commits the new
files to the repo. Vercel auto-redeploys when the push lands and the new
files become readable as bundled deployment assets.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.models import PaperCandidate, PaperSummary


# Repository root is two parents up from src/storage/. Lets the pipeline run
# both from the repo root (`python src/main.py`) and from elsewhere.
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _default_data_dir() -> Path:
	return _REPO_ROOT / "data"


@dataclass
class GitFileStore:
	"""Persists analyses to ``data/`` as plain JSON files.

	``data_dir`` defaults to the ``data/`` directory at the repo root, but
	tests and one-off scripts can pass a temp path.
	"""

	data_dir: Path

	@classmethod
	def from_env(cls) -> "GitFileStore":
		"""Build from the optional ``DATA_DIR`` env var, falling back to
		``<repo>/data``."""
		import os
		override = os.environ.get("DATA_DIR")
		return cls(data_dir=Path(override) if override else _default_data_dir())

	# ------------------------------------------------------------------
	# layout helpers

	def _analyses_dir(self) -> Path:
		return self.data_dir / "analyses"

	def _analysis_path(self, arxiv_id: str) -> Path:
		return self._analyses_dir() / f"{arxiv_id}.json"

	def _index_path(self) -> Path:
		return self.data_dir / "index.json"

	# ------------------------------------------------------------------
	# schema bootstrap — for files, just ``mkdir -p``

	def init_schema(self) -> None:
		self._analyses_dir().mkdir(parents=True, exist_ok=True)
		# Touch index.json if missing so the home page never 404s.
		if not self._index_path().exists():
			self._write_json(self._index_path(), {"papers": [], "updated_at": _now_iso()})

	# ------------------------------------------------------------------
	# writes

	def upsert_paper(self, paper: PaperCandidate, blob_key: Optional[str] = None) -> None:
		"""No-op in this backend — the paper metadata is embedded in the
		analysis payload, so a separate ``papers`` row is unnecessary."""
		return

	def upsert_analysis(
		self,
		summary: PaperSummary,
		payload: Dict[str, Any],
		model: Optional[str] = None,
	) -> None:
		"""Write ``data/analyses/{arxiv_id}.json`` and update the slim index."""
		self.init_schema()

		# 1. Full payload
		path = self._analysis_path(summary.paper.arxiv_id)
		self._write_json(path, {**payload, "model": model, "generated_at": _now_iso()})

		# 2. Slim index entry
		self._update_index(
			{
				"arxiv_id": summary.paper.arxiv_id,
				"topic": summary.topic.name,
				"topic_label": summary.topic.label,
				"title": summary.paper.title,
				"authors": list(summary.paper.authors or [])[:6],
				"score": float(payload.get("score", 0.0)),
				"published": (
					summary.paper.published.strftime("%Y-%m-%d")
					if summary.paper.published else None
				),
				"generated_at": _now_iso(),
			}
		)

	# ------------------------------------------------------------------
	# reads (used by tests and the analyse-one CLI's local preview)

	def get_analysis(
		self, arxiv_id: str, topic: Optional[str] = None
	) -> Optional[Dict[str, Any]]:
		path = self._analysis_path(arxiv_id)
		if not path.is_file():
			return None
		payload = self._read_json(path) or {}
		if topic and payload.get("topic") != topic:
			return None
		return {
			"arxiv_id": arxiv_id,
			"topic": payload.get("topic"),
			"payload": payload,
			"score": float(payload.get("score") or 0.0),
			"model": payload.get("model"),
			"generated_at": payload.get("generated_at"),
		}

	def list_recent_analyses(
		self, limit: int = 50, topic: Optional[str] = None
	) -> List[Dict[str, Any]]:
		index = self._read_json(self._index_path()) or {}
		papers = index.get("papers") or []
		if topic:
			papers = [p for p in papers if p.get("topic") == topic]
		return papers[:limit]

	# Stars live in Vercel KV in production; this local-FS reader is kept
	# only for offline tests that don't want to spin up Redis.

	def list_stars(self) -> List[Dict[str, Any]]:
		path = self.data_dir / "stars.json"
		if not path.is_file():
			return []
		data = self._read_json(path) or {}
		# Stars file shape: {"stars": {"arxiv_id": { topic, note, starred_at }}}
		stars = data.get("stars") or {}
		return [
			{"arxiv_id": k, **(v if isinstance(v, dict) else {})}
			for k, v in stars.items()
		]

	# ------------------------------------------------------------------
	# internal helpers

	def _update_index(self, entry: Dict[str, Any]) -> None:
		path = self._index_path()
		index = self._read_json(path) or {"papers": []}
		papers: List[Dict[str, Any]] = list(index.get("papers") or [])
		# Dedupe on arxiv_id — new entry wins (re-analyses overwrite).
		papers = [p for p in papers if p.get("arxiv_id") != entry["arxiv_id"]]
		papers.insert(0, entry)
		# Sort newest-first to make sure the slim index is always consistent
		# regardless of insertion order.
		papers.sort(
			key=lambda p: (p.get("generated_at") or "", p.get("arxiv_id") or ""),
			reverse=True,
		)
		self._write_json(path, {"papers": papers, "updated_at": _now_iso()})

	@staticmethod
	def _read_json(path: Path) -> Optional[Dict[str, Any]]:
		if not path.is_file():
			return None
		try:
			return json.loads(path.read_text(encoding="utf-8"))
		except Exception:
			return None

	@staticmethod
	def _write_json(path: Path, data: Dict[str, Any]) -> None:
		path.parent.mkdir(parents=True, exist_ok=True)
		# Write atomically: temp file + rename so a crashed mid-write doesn't
		# leave half-baked JSON on disk.
		tmp = path.with_suffix(path.suffix + ".tmp")
		tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
		tmp.replace(path)


def _now_iso() -> str:
	return datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


__all__ = ["GitFileStore"]
