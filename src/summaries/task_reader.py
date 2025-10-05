"""Heuristic answers for TODO-guided reading."""

from __future__ import annotations

import re
from typing import List

from core.models import PaperCandidate


SENTENCE_SPLIT_RE = re.compile(r"(?<=[。！？.!?])\s+")


def _split_sentences(text: str) -> List[str]:
    sentences = [seg.strip() for seg in SENTENCE_SPLIT_RE.split(text.strip()) if seg.strip()]
    if not sentences and text.strip():
        sentences = [text.strip()]
    return sentences


def _best_sentence(question: str, sentences: List[str]) -> str:
    question_lower = question.lower()
    keywords = [word for word in re.split(r"[^\w]+", question_lower) if len(word) > 3]

    best_score = -1
    best_sentence = sentences[0] if sentences else ""
    for sentence in sentences:
        sentence_lower = sentence.lower()
        score = sum(1 for kw in keywords if kw in sentence_lower)
        if score > best_score:
            best_score = score
            best_sentence = sentence

    return best_sentence


def answer_questions(paper: PaperCandidate, questions: List[str]) -> List[str]:
    """Return a short sentence for每个TODO，基于摘要关键词匹配。"""

    sentences = _split_sentences(paper.abstract)
    if not sentences:
        return ["需要阅读原文以获取详细信息。" for _ in questions]

    answers: List[str] = []
    for question in questions:
        sentence = _best_sentence(question, sentences)
        if not sentence:
            answers.append("需要阅读原文以获取详细信息。")
            continue
        answers.append(sentence)

    return answers
