"""Generate TODO-style reading plans for each paper."""

from __future__ import annotations

import json
from typing import List

from core.models import OpenAIConfig, PaperCandidate, SummarizationConfig, TaskItem, TopicConfig

try:  # pragma: no cover - OpenAI optional
	from openai import OpenAI  # type: ignore[import]
except Exception:  # pragma: no cover
	OpenAI = None  # type: ignore[assignment]


DEFAULT_TASKS = [
	("论文要解决的核心问题是什么？", "帮助我判断论文关注的痛点是否与我相关"),
	("作者提出的关键方法/框架是什么？", "确认改进点和技术路线"),
	("相较已有工作，论文的创新点在哪里？", "评估论文的新颖程度"),
	("实验或评估设置如何？", "快速了解验证方式和指标"),
	("有哪些局限性或未来工作方向？", "帮助我决定是否进一步跟进")
]


class TaskPlanner:
	def __init__(self, openai_config: OpenAIConfig, summarization_config: SummarizationConfig, mode: str = "offline"):
		self.openai_config = openai_config
		self.summarization_config = summarization_config
		if mode == "online" and openai_config.api_key and OpenAI is not None:
			self._client = OpenAI(
				api_key=openai_config.api_key,
				base_url=openai_config.base_url or None,
			)
		else:
			self._client = None

	def build_tasks(self, topic: TopicConfig, paper: PaperCandidate) -> List[TaskItem]:
		if self._client is not None:
			try:
				return self._build_with_llm(topic, paper)
			except Exception as exc:  # pragma: no cover
				print(f"[WARN] Task planning via LLM failed ({paper.arxiv_id}): {exc}")

		return self._build_heuristic()

	# ------------------------------------------------------------------

	def _build_with_llm(self, topic: TopicConfig, paper: PaperCandidate) -> List[TaskItem]:
		if self._client is None:
			raise RuntimeError("OpenAI client unavailable")

		# Determine output language instruction
		language_instruction = (
			"Respond in Simplified Chinese (zh-CN)." 
			if self.openai_config.language == "zh-CN" 
			else "Respond in English."
		)

		system_prompt = (
			"You are a research assistant helping users create a reading TODO list from the user's perspective. "
			"Focus on questions that truly impact decision-making. Each TODO should contain 'question' and 'reason' fields. "
			f"Return at most {self.summarization_config.task_list_size} items as a JSON object with a 'todos' key containing an array. "
			f"{language_instruction}"
		)

		payload = {
			"user_interest": topic.interest_prompt,
			"paper_title": paper.title,
			"paper_abstract": paper.abstract,
			"max_items": self.summarization_config.task_list_size,
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
		items = data.get("todos")
		if not isinstance(items, list):
			return self._build_heuristic()

		tasks: List[TaskItem] = []
		for entry in items[: self.summarization_config.task_list_size]:
			if isinstance(entry, dict) and entry.get("question"):
				tasks.append(TaskItem(question=str(entry["question"]).strip(), reason=str(entry.get("reason", "")).strip()))

		return tasks or self._build_heuristic()

	# ------------------------------------------------------------------

	def _build_heuristic(self) -> List[TaskItem]:
		tasks = [TaskItem(question=q, reason=r) for q, r in DEFAULT_TASKS]
		return tasks[: self.summarization_config.task_list_size]
