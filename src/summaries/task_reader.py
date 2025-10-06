"""Execute TODO list by reading paper content."""

from __future__ import annotations

import json
import re
from typing import Any, List, Optional, Tuple

from core.models import (
	CoreSummary,
	OpenAIConfig,
	PaperCandidate,
	SummarizationConfig,
	TaskFinding,
	TaskItem,
)
from fetchers.ar5iv_parser import Ar5ivParser
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

	# ------------------------------------------------------------------

	def analyse(self, paper: PaperCandidate, interest_prompt: str) -> Tuple[Optional[CoreSummary], List[TaskItem], List[TaskFinding], str, str, str]:
		"""
		New workflow:
		1. Fetch paper content
		2. Generate brief summary (Why? What? How?)
		3. Generate core summary (5 aspects: problem, solution, methodology, experiments, conclusion)
		4. Generate interest-based questions from interest_prompt + core summary
		5. Answer questions with quotes
		
		Returns: (core_summary, tasks, findings, overview, brief_summary, markdown)
		"""
		# Import CoreSummary here to avoid circular dependency
		from core.models import CoreSummary, TaskItem

		if paper.arxiv_id.startswith("demo-"):
			markdown = paper.abstract
		else:
			markdown = self.parser.fetch_markdown(paper.arxiv_id)
			if not markdown:
				markdown = self._fallback_to_pdf(paper)
			if not markdown:
				markdown = paper.abstract

		# Step 1: Generate brief summary
		brief_summary = self._generate_brief_summary(paper, [], markdown)
		
		# Step 2: Generate core summary (5 aspects)
		core_summary = self._generate_core_summary(paper, markdown)
		
		# Step 3: Generate interest-based questions
		tasks = self._generate_interest_questions(paper, core_summary, interest_prompt, markdown)
		
		# Step 4: Answer each question with quotes
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

		# Step 5: Build overview from findings
		overview = self._build_overview(paper, findings)
		
		return core_summary, tasks, findings, overview, brief_summary, markdown

	# ------------------------------------------------------------------

	def _answer_with_llm(self, paper: PaperCandidate, task: TaskItem, markdown: str) -> Tuple[str, float]:
		if self._client is None:
			raise RuntimeError("OpenAI client unavailable")

		# Determine output language instruction
		language_instruction = (
			"Respond in Simplified Chinese (zh-CN)" 
			if self.openai_config.language == "zh-CN" 
			else "Respond in English"
		)

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

	def _build_overview(self, paper: PaperCandidate, findings: List[TaskFinding]) -> str:
		"""Build a cohesive narrative overview from findings."""
		if not findings:
			return paper.abstract.strip()
		
		# If we have LLM-generated findings, they should already be comprehensive narratives
		# Simply concatenate them with paragraph breaks
		highlights = [finding.answer for finding in findings if finding.answer and finding.answer.strip()]
		
		if not highlights:
			return paper.abstract.strip()
		
		# Join with double line breaks to create distinct sections
		return "\n\n".join(highlights)

	# ------------------------------------------------------------------

	def _generate_brief_summary(self, paper: PaperCandidate, findings: List[TaskFinding], markdown: str) -> str:
		"""Generate a 1-2 paragraph brief summary answering: Why? What? How?"""
		
		if self._client is None:
			# Fallback: extract 1-2 short paragraphs from abstract
			return self._brief_summary_heuristic(paper.abstract)

		try:
			# Determine output language instruction
			language_instruction = (
				"Respond in Simplified Chinese (zh-CN)"
				if self.openai_config.language == "zh-CN"
				else "Respond in English"
			)

			system_prompt = (
				"You are a research assistant creating narrative paper digests. "
				"Write 1-2 paragraphs (5-8 sentences total) that tell a complete story: "
				"1) Why is this research needed? (problem/motivation), "
				"2) What is proposed? (main contribution), "
				"3) How does it work or what are the results? (method/outcome). "
				"Use paragraph breaks to separate context from key insights. "
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

	def _generate_core_summary(self, paper: PaperCandidate, markdown: str) -> Optional[CoreSummary]:
		"""Generate comprehensive 5-aspect core summary with detailed analysis."""
		
		if self._client is None:
			# Fallback: return None, will be handled gracefully
			return None

		try:
			language_instruction = (
				"Respond in Simplified Chinese (zh-CN)"
				if self.openai_config.language == "zh-CN"
				else "Respond in English"
			)

			system_prompt = (
				"You are an expert research analyst specializing in academic paper review. "
				"Your task is to provide a comprehensive, in-depth analysis of the paper from 5 key perspectives. "
				"Write detailed, professional summaries that capture the full depth of each aspect. "
				"Each section should be substantial (3-8 sentences), providing clear insights and specific details. "
				"Maintain academic rigor while ensuring clarity and readability. "
				"Return JSON with keys: problem, solution, methodology, experiments, conclusion. "
				f"{language_instruction}"
			)

			user_prompt = f"""
Analyze this paper comprehensively from the following 5 perspectives:

1. **Problem**: What is the core problem this paper addresses? Include research gap, motivation, and why this problem matters.

2. **Solution**: What is the proposed solution or main contribution? Describe the key innovation and how it differs from existing approaches.

3. **Methodology**: What are the core methods, techniques, or strategies? Provide detailed explanation of the technical approach, algorithms, or frameworks used. Elaborate on implementation details.

4. **Experiments**: How are the experiments designed? What metrics, baselines, and datasets are used? Include specific numbers and comparison results when available.

5. **Conclusion**: What are the main findings and conclusions? What are the limitations and future directions?

Paper Title: {paper.title}
Paper Abstract: {paper.abstract}
Paper Content: {markdown[:12000]}

Write detailed, comprehensive summaries for each aspect. Ensure logical flow, academic rigor, clarity, and richness of information. Each section should provide substantial insights that help readers deeply understand the paper.

Return as JSON with 5 fields: problem, solution, methodology, experiments, conclusion
"""

			response = self._client.chat.completions.create(
				model=self.openai_config.summarization_model,
				temperature=self.openai_config.temperature,
				response_format={"type": "json_object"},
				messages=[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": user_prompt},
				],
			)

			content = response.choices[0].message.content
			data = json.loads(content or "{}")
			
			return CoreSummary(
				problem=data.get("problem", "No relevant information found").strip(),
				solution=data.get("solution", "No relevant information found").strip(),
				methodology=data.get("methodology", "No relevant information found").strip(),
				experiments=data.get("experiments", "No relevant information found").strip(),
				conclusion=data.get("conclusion", "No relevant information found").strip(),
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
			return [
				TaskItem(question="这篇论文的主要贡献是什么?", reason="理解核心创新点"),
				TaskItem(question="实验结果如何验证了方法的有效性?", reason="评估方法可靠性"),
			]

		try:
			language_instruction = (
				"Respond in Simplified Chinese (zh-CN)"
				if self.openai_config.language == "zh-CN"
				else "Respond in English"
			)

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

			user_prompt = f"""
Paper Title: {paper.title}
Paper Abstract: {paper.abstract}

{core_summary_text}

User's Research Interests: {interest_prompt}

Based on the user's research interests and the paper content, generate 3-5 meaningful, substantive questions that:
1. Are specific and well-targeted
2. Directly relate to the user's research focus
3. Can be comprehensively answered using the paper's content
4. Go beyond surface-level inquiries to probe deeper insights

Return as JSON with 'questions' array, each element has 'question' and 'reason' fields.
"""

			response = self._client.chat.completions.create(
				model=self.openai_config.summarization_model,
				temperature=self.openai_config.temperature,
				response_format={"type": "json_object"},
				messages=[
					{"role": "system", "content": system_prompt},
					{"role": "user", "content": user_prompt},
				],
			)

			content = response.choices[0].message.content
			data = json.loads(content or "{}")
			questions = data.get("questions", [])
			
			tasks = []
			for item in questions[:5]:  # Limit to 5 questions
				q = item.get("question", "").strip()
				r = item.get("reason", "").strip()
				if q:
					tasks.append(TaskItem(question=q, reason=r or "深入理解论文"))
			
			if not tasks:
				# Fallback
				tasks = [
					TaskItem(question="这篇论文的主要贡献是什么?", reason="理解核心创新点"),
					TaskItem(question="实验结果如何验证了方法的有效性?", reason="评估方法可靠性"),
				]
			
			return tasks

		except Exception as exc:
			print(f"[WARN] Interest question generation failed ({paper.arxiv_id}): {exc}")
			return [
				TaskItem(question="这篇论文的主要贡献是什么?", reason="理解核心创新点"),
				TaskItem(question="实验结果如何验证了方法的有效性?", reason="评估方法可靠性"),
			]

	def _answer_with_quotes(self, paper: PaperCandidate, task: TaskItem, markdown: str) -> Tuple[str, float]:
		"""Generate comprehensive answer that naturally integrates evidence from the paper."""
		
		if self._client is None:
			raise RuntimeError("OpenAI client unavailable")

		language_instruction = (
			"Respond in Simplified Chinese (zh-CN)"
			if self.openai_config.language == "zh-CN"
			else "Respond in English"
		)

		system_prompt = (
			"You are an expert research analyst providing comprehensive, evidence-based answers to research questions. "
			"Your task is to write a cohesive, narrative response that naturally integrates direct evidence from the paper. "
			"Weave quotes seamlessly into your analysis rather than listing them separately. "
			"Write 2-4 paragraphs that tell a complete story, citing specific evidence inline. "
			"Use quotation marks for direct quotes and explain their significance in context. "
			"Maintain academic rigor while ensuring the response flows naturally and reads like expert commentary. "
			"If the paper lacks sufficient information, acknowledge this clearly but still provide what insights you can. "
			"Return JSON with 'answer' (the integrated narrative response) and 'confidence' (0-1 float based on evidence quality). "
			f"{language_instruction}"
		)

		user_prompt = f"""
Question: {task.question}
Context/Reason: {task.reason}

Paper Title: {paper.title}
Paper Content: {markdown[:15000]}

Write a comprehensive, narrative response that:
1. Directly addresses the question with specific evidence from the paper
2. Integrates direct quotes naturally within your analysis (use quotation marks for quotes)
3. Explains the significance and implications of the evidence
4. Connects multiple pieces of evidence to form a coherent argument
5. Provides sufficient detail and context for the reader to understand the answer fully

Your response should read like an expert's analysis, not a list of disconnected quotes and statements. Make it engaging and informative.

Return as JSON: {{"answer": "your comprehensive narrative response", "confidence": 0.0-1.0}}
"""

		response = self._client.chat.completions.create(
			model=self.openai_config.summarization_model,
			temperature=self.openai_config.temperature,
			response_format={"type": "json_object"},
			messages=[
				{"role": "system", "content": system_prompt},
				{"role": "user", "content": user_prompt},
			],
		)

		content = response.choices[0].message.content
		data = json.loads(content or "{}")
		
		answer = data.get("answer", "No sufficient information found in the paper.").strip()
		confidence = float(data.get("confidence", 0.5))
		confidence = max(0.0, min(1.0, confidence))
		
		return answer, confidence
