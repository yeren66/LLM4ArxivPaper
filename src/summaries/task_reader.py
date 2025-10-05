"""Execute TODO list by reading paper content."""

from __future__ import annotations

import json
import re
from typing import List, Tuple

from core.models import (
	OpenAIConfig,
	PaperCandidate,
	SummarizationConfig,
	TaskFinding,
	TaskItem,
)
from fetchers.ar5iv_parser import Ar5ivParser

try:  # pragma: no cover
	from openai import OpenAI  # type: ignore[import]
except Exception:  # pragma: no cover
	OpenAI = None  # type: ignore[assignment]


class TaskReader:
	def __init__(
		self,
		parser: Ar5ivParser,
		openai_config: OpenAIConfig,
		summarization_config: SummarizationConfig,
		mode: str = "offline",
	):
		self.parser = parser
		self.openai_config = openai_config
		self.summarization_config = summarization_config

		if mode == "online" and openai_config.api_key and OpenAI is not None:
			self._client = OpenAI(
				api_key=openai_config.api_key,
				base_url=openai_config.base_url or None,
			)
		else:
			self._client = None

	# ------------------------------------------------------------------

	def analyse(self, paper: PaperCandidate, tasks: List[TaskItem]) -> Tuple[List[TaskFinding], str, str]:
		"""Return task findings, overview paragraph, and markdown context."""

		if paper.arxiv_id.startswith("demo-"):
			markdown = paper.abstract
		else:
			markdown = self.parser.fetch_markdown(paper.arxiv_id) or paper.abstract
		findings: List[TaskFinding] = []

		for task in tasks:
			if self._client is not None:
				try:
					answer, confidence = self._answer_with_llm(paper, task, markdown)
				except Exception as exc:  # pragma: no cover
					print(f"[WARN] Task answering via LLM failed ({paper.arxiv_id}): {exc}")
					answer, confidence = self._answer_heuristic(task, markdown)
			else:
				answer, confidence = self._answer_heuristic(task, markdown)

			findings.append(TaskFinding(task=task, answer=answer, confidence=confidence))

		overview = self._build_overview(paper, findings)
		return findings, overview, markdown

	# ------------------------------------------------------------------

	def _answer_with_llm(self, paper: PaperCandidate, task: TaskItem, markdown: str) -> Tuple[str, float]:
		if self._client is None:
			raise RuntimeError("OpenAI client unavailable")

		system_prompt = (
			"你是科研阅读助手，需要根据提供的论文内容解答指定问题。"
			"请给出简洁的段落级回答，并提供 0~1 之间的信心分数。"
			"输出 JSON，包含 answer 与 confidence 字段。"
		)

		payload = {
			"question": task.question,
			"reason": task.reason,
			"paper": {
				"title": paper.title,
				"abstract": paper.abstract,
				"content": markdown,
			},
		}

		response = self._client.chat.completions.create(  # type: ignore[attr-defined]
			model=self.openai_config.summarization_model,
			temperature=self.openai_config.temperature,
			response_format={"type": "json_object"},
			messages=[
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
			],
		)

		content = response.choices[0].message.content  # type: ignore[index]
		data = json.loads(content or "{}")
		answer = str(data.get("answer", "尚未在论文中找到明确答案")).strip()
		confidence = float(data.get("confidence", 0.5))
		confidence = max(0.0, min(1.0, confidence))
		return answer, confidence

	# ------------------------------------------------------------------

	def _answer_heuristic(self, task: TaskItem, markdown: str) -> Tuple[str, float]:
		sentences = self._split_sentences(markdown)
		keywords = [word.strip() for word in re.split(r"[,，;；]", task.question) if word.strip()]

		matched = []
		for sentence in sentences:
			lowered = sentence.lower()
			if any(keyword.lower() in lowered for keyword in keywords):
				matched.append(sentence)
			if len(matched) >= 2:
				break

		if not matched:
			matched = sentences[:1]

		answer = " ".join(matched).strip()
		confidence = 0.4 + 0.3 * len(matched)
		return answer or "暂无充分信息", max(0.0, min(1.0, confidence))

	# ------------------------------------------------------------------

	def _build_overview(self, paper: PaperCandidate, findings: List[TaskFinding]) -> str:
		highlights = [finding.answer for finding in findings[: self.summarization_config.max_sections]]
		highlights = [text for text in highlights if text]
		if not highlights:
			return paper.abstract.strip()
		return "\n".join(highlights)

	@staticmethod
	def _split_sentences(text: str) -> List[str]:
		cleaned = re.sub(r"\s+", " ", text)
		candidates = re.split(r"(?<=[。！？.!?])\s+", cleaned)
		return [sentence.strip() for sentence in candidates if sentence.strip()]
