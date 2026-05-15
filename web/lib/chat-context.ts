/**
 * Build the system prompt that primes the chat LLM with all the context the
 * weekly pipeline already produced for this paper.
 *
 * Rather than replay the full TaskReader transcript (multiple system
 * messages, ~30k tokens of paper body × N calls), we distil the structured
 * output into a single, dense system prompt. The LLM gets the abstract +
 * 5-aspect core summary + the user's interest-targeted Q/A pairs, which
 * covers ~everything the user might want to follow up on.
 *
 * If the user asks something not covered by the digest, the LLM is told it
 * may quote from the raw markdown excerpt — we include the first 12k chars
 * of it as a fallback.
 */

import { pickLang, type AnalysisPayload } from "./data-reader";

const SYSTEM_PREFIX =
  "你是这篇论文的资深研究助手。读者刚刚浏览过下面的结构化分析，并且对其中某些点感到不满意或想要追问。" +
  "回答必须基于论文内容，可在恰当处使用直接引用；如果论文没有充足信息回答问题，请明确说明，不要编造。" +
  "回答使用与用户提问相同的语言（默认简体中文）。";

export function buildChatSystemPrompt(p: AnalysisPayload): string {
  const parts: string[] = [SYSTEM_PREFIX];

  // The analysis is stored bilingually; the chat LLM is happy with English
  // context (and replies in the user's language regardless), so we feed it
  // the English side — it is the grounded original, not a translation.
  const en = (t: Parameters<typeof pickLang>[0]) => pickLang(t, "en");

  parts.push(`\n--- 论文元数据 ---`);
  parts.push(`标题：${p.title}`);
  parts.push(`arXiv ID：${p.arxiv_id}`);
  if (p.authors?.length) parts.push(`作者：${p.authors.join(", ")}`);
  if (p.published) parts.push(`发表日期：${p.published}`);
  if (p.categories?.length) parts.push(`分类：${p.categories.join(", ")}`);

  parts.push(`\n--- 摘要 ---\n${p.abstract}`);

  const brief = en(p.brief_summary);
  if (brief) {
    parts.push(`\n--- 论文速览（已写入网页） ---\n${brief}`);
  }

  if (p.core_summary) {
    parts.push(`\n--- 核心 5 维分析（已写入网页） ---`);
    parts.push(`【1. 解决什么问题】 ${en(p.core_summary.problem)}`);
    parts.push(`【2. 提出什么方案】 ${en(p.core_summary.solution)}`);
    parts.push(`【3. 核心方法】 ${en(p.core_summary.methodology)}`);
    parts.push(`【4. 实验设计】 ${en(p.core_summary.experiments)}`);
    parts.push(`【5. 结论】 ${en(p.core_summary.conclusion)}`);
  }

  if (p.findings?.length) {
    parts.push(`\n--- 已生成的兴趣相关问答 ---`);
    p.findings.forEach((f, i) => {
      parts.push(`Q${i + 1}: ${en(f.question)}`);
      parts.push(`A${i + 1} (信心 ${f.confidence.toFixed(2)}): ${en(f.answer)}`);
    });
  }

  // Fallback: include a chunk of raw markdown so the LLM can dig deeper if
  // asked about something outside the digest.
  if (p.markdown) {
    const excerpt = p.markdown.slice(0, 12_000);
    parts.push(`\n--- 论文正文节选（前 ${excerpt.length} 字，用于追问时引用） ---\n${excerpt}`);
  }

  parts.push(
    "\n回答要求：直接、具体、可验证。优先用论文内的事实；引用时用「」或直接复述。不要在每条回复前重复以上结构化内容。",
  );
  return parts.join("\n");
}
