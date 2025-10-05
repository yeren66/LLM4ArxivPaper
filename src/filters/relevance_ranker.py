"""Relevance scoring for fetched papers."""

from __future__ import annotations

import json
import re
from typing import List

from core.models import (
	DimensionScore,
	OpenAIConfig,
	PaperCandidate,
	RelevanceConfig,
	ScoredPaper,
	TopicConfig,
)

try:  # pragma: no cover - OpenAI is optional for offline smoke tests
	from openai import OpenAI  # type: ignore[import]
except Exception:  # pragma: no cover
	OpenAI = None  # type: ignore[assignment]


class RelevanceRanker:
	"""Compute relevance scores using OpenAI or heuristic fallback."""

	def __init__(self, openai_config: OpenAIConfig, relevance_config: RelevanceConfig, mode: str = "offline"):
		self.openai_config = openai_config
		self.relevance_config = relevance_config
		self.mode = mode

		if mode == "online" and openai_config.api_key and OpenAI is not None:
			self._client = OpenAI(
				api_key=openai_config.api_key,
				base_url=openai_config.base_url or None,
			)
		else:
			self._client = None

	# ------------------------------------------------------------------

	def score(self, topic: TopicConfig, papers: List[PaperCandidate]) -> List[ScoredPaper]:
		scored: List[ScoredPaper] = []
		for paper in papers:
			if self._client is not None:
				try:
					dimension_scores = self._score_with_llm(topic, paper)
				except Exception as exc:  # pragma: no cover - network or parsing error
					print(f"[WARN] LLM relevance scoring failed ({paper.arxiv_id}): {exc}")
					dimension_scores = self._score_heuristic(topic, paper)
			else:
				dimension_scores = self._score_heuristic(topic, paper)

			total_score = sum(score.weight * score.value for score in dimension_scores)
			scored.append(ScoredPaper(paper=paper, scores=dimension_scores, total_score=total_score))

		return scored

	# ------------------------------------------------------------------

	def _score_with_llm(self, topic: TopicConfig, paper: PaperCandidate) -> List[DimensionScore]:
		if self._client is None:
			raise RuntimeError("OpenAI client is not available")

		instructions = (
			"你是科研助理，需要根据用户的兴趣对论文摘要进行相关性评分。"
			"请按照 0~100 的打分标准，给出每个维度的得分和一句理由。"
			"最终仅输出 JSON，键为维度名称，值包含 score 与 reason。"
		)

		dimensions_payload = [
			{
				"name": dim.name,
				"weight": dim.weight,
				"description": dim.description or dim.name,
			}
			for dim in self.relevance_config.dimensions
		]

		user_content = {
			"user_interest": topic.interest_prompt,
			"paper": {
				"title": paper.title,
				"abstract": paper.abstract,
				"categories": paper.categories,
			},
			"dimensions": dimensions_payload,
		}

		response = self._client.chat.completions.create(  # type: ignore[attr-defined]
			model=self.openai_config.relevance_model,
			temperature=self.openai_config.temperature,
			response_format={"type": "json_object"},
			messages=[
				{"role": "system", "content": instructions},
				{"role": "user", "content": json.dumps(user_content, ensure_ascii=False)},
			],
		)

		content = response.choices[0].message.content  # type: ignore[index]
		data = json.loads(content or "{}")

		dimension_scores: List[DimensionScore] = []
		for dim in self.relevance_config.dimensions:
			dim_data = data.get(dim.name, {})
			score_value = float(dim_data.get("score", 0))
			score_value = max(0.0, min(100.0, score_value))
			dimension_scores.append(DimensionScore(name=dim.name, weight=dim.weight, value=score_value / 100.0))

		return dimension_scores

	# ------------------------------------------------------------------

	def _score_heuristic(self, topic: TopicConfig, paper: PaperCandidate) -> List[DimensionScore]:
		text = " ".join([paper.title, paper.abstract]).lower()
		interest = topic.interest_prompt.lower()

		dimension_scores: List[DimensionScore] = []
		for dim in self.relevance_config.dimensions:
			if dim.name == "topic_alignment":
				score = self._keyword_score(topic.query.include, text) * 70 + self._keyword_score(topic.query.categories, text) * 30
			elif dim.name == "methodology_fit":
				score = self._keyword_score(topic.query.include, text + " " + interest) * 80
			elif dim.name == "novelty":
				score = 40 + 60 * self._novelty_hint(text)
			elif dim.name == "experiment_coverage":
				score = 30 + 70 * self._experiment_hint(text)
			else:
				score = 50

			score = max(0.0, min(100.0, score))
			dimension_scores.append(DimensionScore(name=dim.name, weight=dim.weight, value=score / 100.0))

		return dimension_scores

	@staticmethod
	def _keyword_score(keywords: List[str], text: str) -> float:
		if not keywords:
			return 0.5
		hits = sum(1 for keyword in keywords if keyword.lower() in text)
		return min(1.0, hits / max(1, len(keywords)))

	@staticmethod
	def _novelty_hint(text: str) -> float:
		novelty_words = ["novel", "new", "first", "improve", "state-of-the-art"]
		hits = sum(1 for word in novelty_words if word in text)
		return min(1.0, hits / 3)

	@staticmethod
	def _experiment_hint(text: str) -> float:
		experiment_words = ["experiment", "evaluation", "benchmark", "dataset", "ablation"]
		hits = sum(1 for word in experiment_words if word in text)
		return min(1.0, hits / 3)
