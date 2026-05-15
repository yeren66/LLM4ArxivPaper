"""Execute TODO list by reading paper content."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from core.llm_json import chat_json
from core.models import (
	CoreSummary,
	OpenAIConfig,
	PaperCandidate,
	SummarizationConfig,
	TaskFinding,
	TaskItem,
)
from fetchers.ar5iv_parser import Ar5ivParser
from fetchers.pdf_figure import PDFFigureExtractor
from fetchers.pdf_parser import PDFParser

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
		self.mode = mode

		# ar5iv lags arXiv badly for fresh papers, so when it has no figure we
		# fall back to extracting one straight from the PDF.
		self._pdf_figure = PDFFigureExtractor()

		if mode == "online" and openai_config.api_key and OpenAI is not None:
			self._client = OpenAI(
				api_key=openai_config.api_key,
				base_url=openai_config.base_url or None,
			)
		else:
			self._client = None

		if self._client is not None:
			self.pdf_parser = PDFParser(
				openai_client=self._client,
				model=openai_config.summarization_model,
				temperature=openai_config.temperature,
			)
		else:
			self.pdf_parser = None

		# Cache of structured interest profiles keyed by raw interest_prompt
		# text. Each topic's interest_prompt typically stays constant across a
		# pipeline run, so structuring it once per process saves an LLM call
		# per paper.
		self._interest_cache: dict[str, dict] = {}

	# ------------------------------------------------------------------

	def analyse(self, paper: PaperCandidate, interest_prompt: str) -> Tuple[Optional[CoreSummary], List[TaskItem], List[TaskFinding], str, str, str, Optional["PaperFigure"], Optional[dict]]:
		"""
		Pipeline:
		1. Fetch paper content (ar5iv → pdf → abstract fallback) + the method figure
		2. Core summary (problem / solution / methodology+figure / experiments)
		3. Interest-driven questions
		4. Answer each with quoted evidence
		5. Findings & summary: rewrite the 5th aspect to fold in the answers
		6. Brief summary (1-2 paragraphs)
		7. Relevance note (1-2 sentences — why this paper matters to YOUR work)
		8. Translation: everything above is generated in English (papers are
		   English, LLMs are strongest there); when openai.language != "en" a
		   single follow-up call translates the whole bundle into it.

		Returns: (core_summary, tasks, findings, brief_summary, markdown,
		          relevance, figure, translations)
		``translations`` is None for English-only instances.
		"""
		# Import here to avoid circular dependency
		from core.models import CoreSummary, TaskItem, PaperFigure

		figure: Optional[PaperFigure] = None
		if paper.arxiv_id.startswith("demo-"):
			markdown = paper.abstract
		else:
			markdown = self.parser.fetch_markdown(paper.arxiv_id)
			# Pull the single method figure from the same (cached) ar5iv HTML.
			# Best-effort — failure just means no figure.
			try:
				figure = self.parser.fetch_method_figure(paper.arxiv_id)
			except Exception as exc:  # pragma: no cover
				print(f"[WARN] Figure extraction failed ({paper.arxiv_id}): {exc}")
			# ar5iv usually has nothing for a just-published paper; fall back
			# to rendering the figure straight out of the PDF.
			if figure is None and paper.pdf_url:
				print(f"[INFO] No ar5iv figure for {paper.arxiv_id}; trying PDF extraction.")
				try:
					figure = self._pdf_figure.fetch(paper.pdf_url, paper.arxiv_id)
				except Exception as exc:  # pragma: no cover
					print(f"[WARN] PDF figure extraction failed ({paper.arxiv_id}): {exc}")
			if not markdown:
				markdown = self._fallback_to_pdf(paper)
			if not markdown:
				markdown = paper.abstract

		# Step 1: Core summary. The methodology aspect weaves in the method
		# figure (caption + the paper's own text describing it).
		core_summary = self._generate_core_summary(paper, markdown, figure)

		# Step 2: Interest-targeted questions.
		tasks = self._generate_interest_questions(paper, core_summary, interest_prompt, markdown)

		# Step 3: Answer each question with quotes.
		findings: List[TaskFinding] = []
		for task in tasks:
			if self._client is not None:
				try:
					answer, confidence = self._answer_with_quotes(paper, task, markdown)
				except Exception as exc:  # pragma: no cover
					print(f"[WARN] Task answering via LLM failed ({paper.arxiv_id}): {exc}")
					answer, confidence = self._answer_heuristic(task, markdown)
			else:
				answer, confidence = self._answer_heuristic(task, markdown)

			findings.append(TaskFinding(task=task, answer=answer, confidence=confidence))

		# Step 4: Findings & summary — rewrite the 5th core aspect so it folds
		# in what the interest Q&A turned up. Kept short.
		if core_summary is not None:
			core_summary.conclusion = self._generate_findings_summary(
				paper, core_summary, findings
			)

		# Step 5: Brief summary — 1-2 paragraphs, leans on core + findings.
		brief_summary = self._generate_brief_summary(paper, findings, markdown, core_summary=core_summary)

		# Step 6: Relevance note — why a reader with THESE interests should care.
		relevance = self._generate_relevance(paper, core_summary, brief_summary, interest_prompt)

		# Step 7: Translation. Everything above is English; if the instance is
		# configured for another language, translate the whole bundle in one
		# call (it only sees the distilled summary, never the paper body, so
		# it is cheap and high-fidelity).
		translations = self._translate_bundle(
			paper, core_summary, findings, brief_summary, relevance, figure
		)

		return core_summary, tasks, findings, brief_summary, markdown, relevance, figure, translations

	# ------------------------------------------------------------------

	# Map of openai.language values to a human language name for the prompt.
	_LANGUAGE_NAMES = {
		"zh-CN": "Simplified Chinese (zh-CN)",
		"zh": "Simplified Chinese (zh-CN)",
	}

	def _translate_bundle(
		self,
		paper: PaperCandidate,
		core_summary: Optional["CoreSummary"],
		findings: List[TaskFinding],
		brief_summary: str,
		relevance: str,
		figure: Optional["PaperFigure"] = None,
	) -> Optional[dict]:
		"""Translate the whole English analysis bundle into openai.language.

		Returns a dict mirroring the English fields, or None when no
		translation is needed (English instance) or possible (offline / on
		error). Only the distilled summary is sent — never the paper body —
		so this is a small, cheap call.
		"""
		lang = (self.openai_config.language or "en").strip()
		if lang.lower().startswith("en"):
			return None
		if self._client is None:
			return None

		target = self._LANGUAGE_NAMES.get(lang, lang)

		bundle: Dict[str, Any] = {
			"brief_summary": brief_summary or "",
			"relevance": relevance or "",
			"findings": [
				{
					"question": f.task.question,
					"reason": f.task.reason,
					"answer": f.answer,
				}
				for f in findings
			],
		}
		if core_summary is not None:
			bundle["core_summary"] = {
				"problem": core_summary.problem,
				"solution": core_summary.solution,
				"methodology": core_summary.methodology,
				"experiments": core_summary.experiments,
				"conclusion": core_summary.conclusion,
			}
		# The figure's caption is shown on the paper page, so it should follow
		# the language too. (label / reference_text are not displayed, so they
		# stay English.)
		if figure is not None and (figure.caption or "").strip():
			bundle["figure_caption"] = figure.caption

		system_prompt = (
			f"You translate an academic paper analysis from English into {target}. "
			"Translate every string value into natural, fluent, idiomatic "
			f"{target} as a researcher would write it. Keep technical terms, "
			"proper nouns, model/benchmark/metric names and numbers intact "
			"(e.g. BLEU, SWE-bench, Pass@1, F1, GPU) — translate around them. "
			"Do NOT summarise, expand, reorder or omit anything. Return a JSON "
			"object with EXACTLY the same keys and the same array lengths as "
			"the input; only the string values change."
		)
		user_prompt = (
			f"Translate the string values of this JSON into {target}, keeping "
			"the structure identical:\n\n"
			+ json.dumps(bundle, ensure_ascii=False)
		)

		try:
			data = chat_json(
				self._client,
				self.openai_config.summarization_model,
				[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": user_prompt},
				],
				temperature=0.2,
			)
		except Exception as exc:  # pragma: no cover - network / parse issues
			print(f"[WARN] Translation failed ({paper.arxiv_id}): {exc}")
			return None

		# Validate shape; fall back to English per-field on any mismatch so a
		# sloppy translation can never blank out content.
		result: Dict[str, Any] = {}
		result["brief_summary"] = str(data.get("brief_summary") or brief_summary or "").strip()
		result["relevance"] = str(data.get("relevance") or relevance or "").strip()

		if "core_summary" in bundle:
			src = bundle["core_summary"]
			tr = data.get("core_summary") or {}
			result["core_summary"] = {
				key: str(tr.get(key) or src[key] or "").strip() for key in src
			}

		if "figure_caption" in bundle:
			result["figure_caption"] = str(
				data.get("figure_caption") or bundle["figure_caption"] or ""
			).strip()

		tr_findings = data.get("findings")
		out_findings = []
		for i, f in enumerate(findings):
			tf = tr_findings[i] if isinstance(tr_findings, list) and i < len(tr_findings) else {}
			out_findings.append(
				{
					"question": str(tf.get("question") or f.task.question or "").strip(),
					"reason": str(tf.get("reason") or f.task.reason or "").strip(),
					"answer": str(tf.get("answer") or f.answer or "").strip(),
				}
			)
		result["findings"] = out_findings
		return result

	# ------------------------------------------------------------------

	def _answer_with_llm(self, paper: PaperCandidate, task: TaskItem, markdown: str) -> Tuple[str, float]:
		if self._client is None:
			raise RuntimeError("OpenAI client unavailable")

		# Analysis is always generated in English; a later pass translates it.
		language_instruction = "Respond in English."

		system_prompt = (
			"You are a research reading assistant. Based on the provided paper content, answer the specified question concisely. "
			"Provide a paragraph-level response and a confidence score between 0 and 1. "
			f"Output JSON with 'answer' and 'confidence' fields. {language_instruction}"
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
		answer = str(data.get("answer", "No clear answer found in the paper yet")).strip()
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
		return answer or "No sufficient information", max(0.0, min(1.0, confidence))

	# ------------------------------------------------------------------

	def _generate_findings_summary(
		self,
		paper: PaperCandidate,
		core_summary: "CoreSummary",
		findings: List[TaskFinding],
	) -> str:
		"""The 5th core aspect, "Findings & Summary": the paper's own
		conclusion folded together with what the interest-driven Q&A turned
		up. Deliberately short — the detailed Q&A lives in its own section.
		"""
		paper_conclusion = (core_summary.conclusion or "").strip()
		if self._client is None:
			return paper_conclusion or paper.abstract.strip()[:300]

		language_instruction = "Write in English."
		findings_text = "\n".join(
			f"- Q: {f.task.question}\n  A: {f.answer}" for f in findings[:5]
		)
		system_prompt = (
			"You are summarising a paper for a researcher. Write a SHORT "
			"'findings and takeaways' paragraph (3-5 sentences, no more) that "
			"combines the paper's own conclusion with the most important "
			"points surfaced by the interest-driven Q&A. State what was found "
			"and what it means for the reader; do not repeat the Q&A verbatim. "
			"Plain prose, no markdown, no bullet list. "
			f"{language_instruction}"
		)
		user_prompt = (
			f"Paper: {paper.title}\n\n"
			f"Paper's own conclusion:\n{paper_conclusion}\n\n"
			f"Interest-driven Q&A:\n{findings_text}"
		)
		try:
			response = self._client.chat.completions.create(  # type: ignore[attr-defined]
				model=self.openai_config.summarization_model,
				temperature=self.openai_config.temperature,
				messages=[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": user_prompt},
				],
			)
			content = (response.choices[0].message.content or "").strip()
			return content or paper_conclusion
		except Exception as exc:  # pragma: no cover
			print(f"[WARN] Findings summary failed ({paper.arxiv_id}): {exc}")
			return paper_conclusion or paper.abstract.strip()[:300]

	# ------------------------------------------------------------------

	def _generate_brief_summary(
		self,
		paper: PaperCandidate,
		findings: List[TaskFinding],
		markdown: str,
		core_summary: Optional["CoreSummary"] = None,
	) -> str:
		"""Generate a 1-2 paragraph brief summary answering: Why? What? How?

		Called LAST in :meth:`analyse` so it can lean on the structured core
		summary and interest-driven findings instead of re-reading the full
		paper from scratch.
		"""

		if self._client is None:
			# Fallback: extract 1-2 short paragraphs from abstract
			return self._brief_summary_heuristic(paper.abstract)

		try:
			language_instruction = "Respond in English."

			system_prompt = (
				"You are a research assistant creating narrative paper digests. "
				"Write 1-2 paragraphs (5-8 sentences total) that tell a complete story: "
				"1) Why is this research needed? (problem/motivation), "
				"2) What is proposed? (main contribution), "
				"3) How does it work or what are the results? (method/outcome). "
				"Use paragraph breaks to separate context from key insights. "
				"Lean on the provided core_summary and findings rather than the raw paper text. "
				f"Keep it clear and engaging. {language_instruction}"
			)

			# Collect key findings as context
			findings_text = "\n".join(
				[
					f"Q: {f.task.question}\nA: {f.answer}"
					for f in findings[:3]  # Use first 3 findings
				]
			)

			payload = {
				"paper_title": paper.title,
				"paper_abstract": paper.abstract,
				"core_summary": (
					{
						"problem": core_summary.problem,
						"solution": core_summary.solution,
						"methodology": core_summary.methodology,
						"experiments": core_summary.experiments,
						"conclusion": core_summary.conclusion,
					}
					if core_summary else None
				),
				"key_findings": findings_text,
			}

			response = self._client.chat.completions.create(  # type: ignore[attr-defined]
				model=self.openai_config.summarization_model,
				temperature=self.openai_config.temperature,
				messages=[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
				],
			)

			content = response.choices[0].message.content  # type: ignore[index]
			return (content or "").strip() or self._brief_summary_heuristic(paper.abstract)

		except Exception as exc:  # pragma: no cover
			print(f"[WARN] Brief summary generation failed ({paper.arxiv_id}): {exc}")
			return self._brief_summary_heuristic(paper.abstract)

	@staticmethod
	def _brief_summary_heuristic(abstract: str) -> str:
		"""Fallback: extract 1-2 paragraphs from abstract."""
		sentences = [s for s in re.split(r'(?<=[.!?])\s+', abstract) if s.strip()]
		if not sentences:
			return abstract.strip()[:400]
		first_chunk = " ".join(sentences[:3]).strip()
		second_chunk = " ".join(sentences[3:6]).strip()
		if second_chunk:
			return f"{first_chunk}\n\n{second_chunk}"
		return first_chunk

	# ------------------------------------------------------------------

	def _generate_relevance(
		self,
		paper: PaperCandidate,
		core_summary: Optional["CoreSummary"],
		brief_summary: str,
		interest_prompt: str,
	) -> str:
		"""1-2 sentence note answering 'why does this paper matter to *me*?'

		Different from brief_summary, which is about the paper itself. This
		note explicitly bridges the paper's contribution to the user's stated
		research interests (the topic's ``interest_prompt``). Shown at the
		very top of the paper page so the reader knows in 5 seconds whether
		to keep reading.
		"""
		if self._client is None:
			return self._relevance_heuristic(paper.abstract, interest_prompt)

		# Reuse the cached structured interest profile when available; the
		# question generator already populated it for this topic.
		interest_profile = self.get_structured_interest(interest_prompt) if interest_prompt else {}

		try:
			language_instruction = "Write in English, 1-2 sentences, ~120-260 characters."
			system_prompt = (
				"You are an experienced research advisor. The reader has stated "
				"specific research interests. Your job is to answer, in 1-2 short "
				"sentences, the question: 'Why might THIS paper matter to a "
				"researcher with THOSE interests?' "
				"Do NOT just summarise the paper. Instead, draw an explicit bridge: "
				"name the part of the paper that connects to the reader's interest, "
				"and say whether it confirms / extends / challenges / is tangential "
				"to the reader's direction. If the connection is weak or only "
				"surface-level (e.g. shares a keyword but the actual contributions "
				"are unrelated), say so honestly — don't oversell. "
				"Output plain prose, no markdown, no bullet points, no quotes. "
				f"{language_instruction}"
			)
			user_payload = {
				"reader_interests_raw": interest_prompt,
				"reader_interests_structured": interest_profile,
				"paper_title": paper.title,
				"paper_abstract": paper.abstract,
				"brief_summary": brief_summary,
				"core_summary": (
					{
						"problem": core_summary.problem,
						"solution": core_summary.solution,
						"methodology": core_summary.methodology,
					}
					if core_summary
					else None
				),
			}
			response = self._client.chat.completions.create(  # type: ignore[attr-defined]
				model=self.openai_config.summarization_model,
				temperature=0.3,
				messages=[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
				],
			)
			content = (response.choices[0].message.content or "").strip()
			content = content.strip("\"' ")
			return content or self._relevance_heuristic(paper.abstract, interest_prompt)
		except Exception as exc:  # pragma: no cover
			print(f"[WARN] Relevance note generation failed ({paper.arxiv_id}): {exc}")
			return self._relevance_heuristic(paper.abstract, interest_prompt)

	def _relevance_heuristic(self, abstract: str, interest_prompt: str) -> str:
		"""Fallback when no LLM is available. Always English — the analysis is
		generated in English (and translated by a later LLM call, which is
		unavailable in offline mode anyway)."""
		if interest_prompt:
			return "(Online LLM not enabled — relevance note unavailable. See the 5-aspect core below to judge how this paper relates to your work.)"
		return "(Online LLM not enabled.)"

	def _fallback_questions(self) -> List[TaskItem]:
		"""Generic interest questions used when the LLM is unavailable or
		returns nothing. Always English, like the rest of the analysis."""
		return [
			TaskItem(
				question="What is the main contribution of this paper?",
				reason="Understand the core innovation",
			),
			TaskItem(
				question="How do the experiments validate the method's effectiveness?",
				reason="Assess the method's reliability",
			),
		]

	@staticmethod
	def _split_sentences(text: str) -> List[str]:
		cleaned = re.sub(r"\s+", " ", text)
		candidates = re.split(r"(?<=[。！？.!?])\s+", cleaned)
		return [sentence.strip() for sentence in candidates if sentence.strip()]

	def _fallback_to_pdf(self, paper: PaperCandidate) -> Optional[str]:
		"""Fallback to PDF parsing if ar5iv markdown fetching fails."""
		if self.pdf_parser is None or not paper.pdf_url:
			return None

		try:
			pdf_content = self.pdf_parser.fetch_text_from_pdf(paper.pdf_url)
			return pdf_content or None
		except Exception as e:  # pragma: no cover
			print(f"[WARN] PDF fallback failed for {paper.arxiv_id}: {e}")
			return None

	# ------------------------------------------------------------------
	# New methods for restructured workflow
	# ------------------------------------------------------------------

	def _generate_core_summary(
		self,
		paper: PaperCandidate,
		markdown: str,
		figure: Optional["PaperFigure"] = None,
	) -> Optional[CoreSummary]:
		"""Generate the 5-aspect core summary.

		The methodology aspect weaves in the method figure: when a figure is
		available, the prompt gets its caption plus the paper's own text
		describing it, and is told to explain what the diagram depicts as
		part of the methodology. The 5th aspect (`conclusion`) is a starting
		point — :meth:`_generate_findings_summary` rewrites it later.
		"""
		if self._client is None:
			return None

		try:
			language_instruction = "Respond in English."

			system_prompt = (
				"You are a research analyst. Summarise the paper from 5 angles. "
				"Each aspect must be thorough and self-contained — a reader should "
				"understand that aspect of the paper WITHOUT opening the original. "
				"Aim for a substantial paragraph per aspect (methodology usually "
				"needs more); go into the actual mechanism, the algorithm steps, "
				"the concrete design choices, the specific datasets / baselines / "
				"metrics / numbers. Depth comes from real specifics, NOT from "
				"padding: do not restate the abstract, do not repeat the same "
				"point across aspects, do not write generic filler sentences. If "
				"a detail is in the paper, include it; if it genuinely isn't, "
				"don't invent it. "
				"Return JSON with keys: problem, solution, methodology, experiments, conclusion. "
				f"{language_instruction}"
			)

			figure_block = ""
			if figure is not None:
				figure_block = (
					"\n\nMethod figure (describe what it depicts as part of the "
					f"methodology aspect):\n- Caption: {figure.caption}\n"
					f"- The paper's own description of it: {figure.reference_text or '(none)'}"
				)

			user_prompt = f"""Summarise this paper from 5 angles. Each should be a
substantial, self-contained explanation — not a one-liner.

1. problem — the core problem and the concrete gap in prior work; what
   specifically was missing or broken, and why it matters in practice.
2. solution — the main contribution and how it actually differs from prior
   work; the key idea/insight that makes it work, stated precisely.
3. methodology — the full technical approach: the pipeline or framework, the
   algorithm steps, the model/architecture choices, the inputs and outputs,
   any important hyperparameters or design decisions. This is the longest
   aspect. If a method figure is provided below, explain what it depicts as
   part of this walkthrough.
4. experiments — the setup in detail: datasets, baselines compared against,
   metrics, ablations, and the concrete result numbers (state the actual
   figures, not just "outperforms").
5. conclusion — the main findings, what they imply, and the stated
   limitations (this aspect is refined later, so keep it focused).

Title: {paper.title}
Abstract: {paper.abstract}
Content: {markdown[:self.summarization_config.max_content_chars]}{figure_block}

Return JSON with 5 fields: problem, solution, methodology, experiments, conclusion."""

			data = chat_json(
				self._client,
				self.openai_config.summarization_model,
				[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": user_prompt},
				],
				temperature=self.openai_config.temperature,
			)

			return CoreSummary(
				problem=str(data.get("problem", "No relevant information found")).strip(),
				solution=str(data.get("solution", "No relevant information found")).strip(),
				methodology=str(data.get("methodology", "No relevant information found")).strip(),
				experiments=str(data.get("experiments", "No relevant information found")).strip(),
				conclusion=str(data.get("conclusion", "No relevant information found")).strip(),
			)

		except Exception as exc:
			print(f"[WARN] Core summary generation failed ({paper.arxiv_id}): {exc}")
			return None

	def _generate_interest_questions(
		self, 
		paper: PaperCandidate, 
		core_summary: Optional[CoreSummary],
		interest_prompt: str,
		markdown: str
	) -> List[TaskItem]:
		"""Generate interest-based questions from user's interest_prompt and core summary."""
		
		if self._client is None or not interest_prompt:
			# Fallback: generate generic questions
			return self._fallback_questions()

		try:
			language_instruction = "Respond in English."

			system_prompt = (
				"You are an expert research consultant helping researchers identify key questions about academic papers. "
				"Based on the user's specific research interests and the paper's core content, "
				"generate 3-5 insightful, specific questions that align with the user's research focus. "
				"Questions should be substantive, thought-provoking, and directly answerable from the paper content. "
				"Return JSON with 'questions' array, each item has 'question' and 'reason' fields. "
				f"{language_instruction}"
			)

			core_summary_text = ""
			if core_summary:
				core_summary_text = f"""
Paper Core Summary:
- Problem: {core_summary.problem[:300]}...
- Solution: {core_summary.solution[:300]}...
- Methodology: {core_summary.methodology[:300]}...
- Experiments: {core_summary.experiments[:300]}...
- Conclusion: {core_summary.conclusion[:300]}...
"""

			# Structured interest profile (cached across papers) gives the
			# LLM hard guidance about the user's research questions and the
			# keywords that signal alignment, instead of a free-text blob.
			interest_profile = self.get_structured_interest(interest_prompt)

			user_prompt = f"""
Paper Title: {paper.title}
Paper Abstract: {paper.abstract}

{core_summary_text}

User's Research Interests (raw):
{interest_prompt}

Structured Interest Profile (derived once per topic):
- Distilled summary: {interest_profile.get("summary", "")}
- Open research questions: {interest_profile.get("research_questions", [])}
- Must-have keywords: {interest_profile.get("must_have_keywords", [])}
- Anti-keywords (should NOT drive a question): {interest_profile.get("anti_keywords", [])}

Based on the structured interest profile and the paper content, generate 3-5 meaningful, substantive questions that:
1. Are specific and well-targeted
2. Directly probe one of the user's research questions or keyword themes
3. Can be comprehensively answered using the paper's content
4. Go beyond surface-level inquiries to probe deeper insights
5. Avoid questions that are only tangentially related to the user's interest

Return as JSON with 'questions' array, each element has 'question' and 'reason' fields.
"""

			data = chat_json(
				self._client,
				self.openai_config.summarization_model,
				[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": user_prompt},
				],
				temperature=self.openai_config.temperature,
			)
			questions = data.get("questions", [])
			
			default_reason = "Deepen understanding of the paper"
			tasks = []
			for item in questions[:5]:  # Limit to 5 questions
				q = item.get("question", "").strip()
				r = item.get("reason", "").strip()
				if q:
					tasks.append(TaskItem(question=q, reason=r or default_reason))

			if not tasks:
				tasks = self._fallback_questions()

			return tasks

		except Exception as exc:
			print(f"[WARN] Interest question generation failed ({paper.arxiv_id}): {exc}")
			return self._fallback_questions()

	def _answer_with_quotes(self, paper: PaperCandidate, task: TaskItem, markdown: str) -> Tuple[str, float]:
		"""Generate comprehensive answer that naturally integrates evidence from the paper."""
		
		if self._client is None:
			raise RuntimeError("OpenAI client unavailable")

		language_instruction = "Respond in English."

		system_prompt = (
			"You answer a research question about a paper using evidence from "
			"its text. Write 1-2 tight paragraphs (not more), weaving in direct "
			"quotes inline with quotation marks. Be specific, skip the padding. "
			"If the paper doesn't really address the question, say so plainly. "
			"Return JSON with 'answer' and 'confidence' (0-1 float). "
			"Confidence rubric: 1.0 = directly supported by inline quotes; "
			"0.7 = inferable from two or more passages; "
			"0.4 = mostly inferred from the abstract; "
			"below 0.3 = speculative, the paper doesn't really address it. "
			f"{language_instruction}"
		)

		user_prompt = f"""Question: {task.question}
Context: {task.reason}

Paper Title: {paper.title}
Paper Content: {markdown[:self.summarization_config.max_content_chars]}

Answer the question directly with specific evidence, quoting inline where it helps. 1-2 paragraphs.

Return JSON: {{"answer": "...", "confidence": 0.0-1.0}}"""

		data = chat_json(
			self._client,
			self.openai_config.summarization_model,
			[
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": user_prompt},
			],
			temperature=self.openai_config.temperature,
		)

		answer = str(data.get("answer", "No sufficient information found in the paper.")).strip()
		confidence = float(data.get("confidence", 0.5))
		confidence = max(0.0, min(1.0, confidence))

		return answer, confidence

	# ------------------------------------------------------------------
	# Structured interest profile (cached per interest_prompt string)
	#
	# A topic's interest_prompt is free text written by the user. Sending the
	# raw text into the relevance ranker and question generator is noisy. We
	# pay one LLM call per *unique* prompt to derive a structured profile
	# (research questions, must-have / anti keywords) and reuse it across all
	# papers in the topic. The cache is scoped to this TaskReader instance,
	# i.e. one pipeline run.
	# ------------------------------------------------------------------

	def get_structured_interest(self, interest_prompt: str) -> Dict[str, Any]:
		"""Return a structured view of ``interest_prompt`` (cached)."""

		key = (interest_prompt or "").strip()
		if not key:
			return {"summary": "", "research_questions": [], "must_have_keywords": [], "anti_keywords": []}

		cached = self._interest_cache.get(key)
		if cached is not None:
			return cached

		if self._client is None:
			result = {
				"summary": key,
				"research_questions": [],
				"must_have_keywords": [],
				"anti_keywords": [],
			}
			self._interest_cache[key] = result
			return result

		language_instruction = "Field values should be in English"

		system_prompt = (
			"You are a research advisor extracting a structured interest profile from a "
			"researcher's free-text description of what they care about. "
			"Output a JSON object with exactly these keys: "
			"  summary (one-sentence distillation, <= 25 words), "
			"  research_questions (3-6 specific open questions implied by the description), "
			"  must_have_keywords (3-8 short noun phrases or technical terms that a relevant paper would mention), "
			"  anti_keywords (0-5 phrases that would make a paper a poor match, e.g. unrelated subfields). "
			f"{language_instruction}. Do not invent topics the user did not allude to."
		)

		try:
			data = chat_json(
				self._client,
				self.openai_config.summarization_model,
				[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": f"Researcher's interest description:\n\n{key}"},
				],
				temperature=0.0,
			)
			result = {
				"summary": str(data.get("summary") or "").strip()[:300],
				"research_questions": [str(q).strip() for q in (data.get("research_questions") or [])][:6],
				"must_have_keywords": [str(k).strip() for k in (data.get("must_have_keywords") or [])][:8],
				"anti_keywords": [str(k).strip() for k in (data.get("anti_keywords") or [])][:5],
			}
		except Exception as exc:  # pragma: no cover
			print(f"[WARN] Structured interest extraction failed: {exc}")
			result = {
				"summary": key,
				"research_questions": [],
				"must_have_keywords": [],
				"anti_keywords": [],
			}

		self._interest_cache[key] = result
		return result
