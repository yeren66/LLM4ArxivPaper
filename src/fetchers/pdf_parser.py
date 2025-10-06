"""Parse PDF papers by sending them directly to LLM for extraction."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Optional

try:  # pragma: no cover
	import requests  # type: ignore[import]
except Exception:  # pragma: no cover
	requests = None  # type: ignore[assignment]

try:  # pragma: no cover
	from openai import OpenAI  # type: ignore[import]
except Exception:  # pragma: no cover
	OpenAI = None  # type: ignore[assignment]


class PDFParser:
	"""Download PDF and extract text content using OpenAI API."""

	def __init__(self, openai_client: Optional[object] = None, timeout: int = 30, model: Optional[str] = None, temperature: float = 0.2):
		"""
		Initialize PDF parser.
		
		Args:
			openai_client: OpenAI client instance for PDF parsing
			timeout: Request timeout in seconds
			model: Model to use for parsing
			temperature: Sampling temperature for the model
		"""
		self.client = openai_client
		self.timeout = timeout
		self.model = model
		self.temperature = temperature

	def fetch_text_from_pdf(self, pdf_url: str, max_chars: int = 15000) -> Optional[str]:
		"""
		Download PDF and extract text content using LLM.
		
		Args:
			pdf_url: Direct URL to the PDF file
			max_chars: Maximum characters to return (truncate if longer)
			
		Returns:
			Extracted text content or None if failed
		"""
		if requests is None or self.client is None or not self.model:
			print("[WARN] requests, OpenAI client, or model unavailable; skipping PDF parsing.")
			return None

		tmp_path: Optional[str] = None
		try:
			print(f"[INFO] Downloading PDF from {pdf_url}")
			response = requests.get(pdf_url, timeout=self.timeout)
			response.raise_for_status()

			with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
				tmp_file.write(response.content)
				tmp_path = tmp_file.name

			print("[INFO] PDF downloaded, attempting to parse with LLM...")
			text_content = self._parse_with_llm(tmp_path)

			if text_content and len(text_content) > max_chars:
				text_content = text_content[:max_chars] + "\n\n... (content truncated)"

			return text_content

		except Exception as exc:  # pragma: no cover
			print(f"[WARN] Failed to parse PDF from {pdf_url}: {exc}")
			return None
		finally:
			if tmp_path:
				Path(tmp_path).unlink(missing_ok=True)

	def _parse_with_llm(self, pdf_path: str) -> Optional[str]:
		"""
		Parse PDF using OpenAI API with file upload support.
		
		Note: Requires models that support file attachments (e.g., gpt-4o / gpt-4.1).
		"""
		if self.client is None or not self.model:
			return None

		uploaded_file_id: Optional[str] = None
		try:
			with open(pdf_path, "rb") as file_handle:
				uploaded = self.client.files.create(file=file_handle, purpose="assistants")  # type: ignore[attr-defined]
				uploaded_file_id = getattr(uploaded, "id", None)

			prompt = (
				"Extract the main textual content from the attached academic PDF. "
				"Return a concise markdown rendition preserving section order. "
				"Focus on equations, methods, and results; omit boilerplate such as author metadata."
			)

			response = self.client.responses.create(  # type: ignore[attr-defined]
				model=self.model,
				temperature=self.temperature,
				input=[
					{
						"role": "user",
						"content": [
							{"type": "input_text", "text": prompt},
							{"type": "input_file", "file_id": uploaded_file_id},
						],
					}
				],
			)

			return self._extract_output_text(response)

		except Exception as exc:  # pragma: no cover
			print(f"[WARN] LLM-based PDF parsing failed: {exc}")
			return None
		finally:
			if uploaded_file_id:
				try:
					self.client.files.delete(uploaded_file_id)  # type: ignore[attr-defined]
				except Exception:
					pass

	@staticmethod
	def _extract_output_text(response: Any) -> Optional[str]:
		"""Extract textual content from OpenAI response objects."""
		if response is None:
			return None

		# Prefer direct attribute if available
		text_segments = []
		output_text = getattr(response, "output_text", None)
		if isinstance(output_text, str) and output_text.strip():
			text_segments.append(output_text.strip())

		data: Any
		if hasattr(response, "model_dump"):
			data = response.model_dump()
		elif hasattr(response, "to_dict"):
			data = response.to_dict()  # type: ignore[assignment]
		else:
			data = response

		text_segments.extend(PDFParser._extract_from_node(data))

		combined = "\n".join(segment.strip() for segment in text_segments if segment and segment.strip())
		return combined or None

	@staticmethod
	def _extract_from_node(node: Any) -> list[str]:
		"""Recursively extract text fields from nested response structures."""
		results: list[str] = []

		if isinstance(node, dict):
			for key, value in node.items():
				if key in {"text", "value"} and isinstance(value, str):
					results.append(value)
				else:
					results.extend(PDFParser._extract_from_node(value))
		elif isinstance(node, list):
			for item in node:
				results.extend(PDFParser._extract_from_node(item))

		return results
