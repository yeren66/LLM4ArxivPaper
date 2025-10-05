"""Build markdown summaries for processed papers."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from core.models import PaperCandidate, PaperSummary


def _join_section(title: str, items: List[str]) -> str:
    if not items:
        return ""
    bullet_lines = "\n".join(f"- {item}" for item in items)
    return f"## {title}\n\n{bullet_lines}\n"


def build_summary(
    paper: PaperCandidate,
    todo: List[str],
    findings: List[str],
    *,
    topic_label: str,
    score: Optional[float] = None,
) -> PaperSummary:
    """Construct a ``PaperSummary`` with simple markdown output."""

    conclusion = findings[0] if findings else "建议深入阅读全文以确认细节。"

    meta_lines = [f"- 主题：{topic_label}"]
    if score is not None:
        meta_lines.append(f"- 相关性评分：{score:.1f}")
    if paper.published:
        meta_lines.append(f"- 发表日期：{paper.published.strftime('%Y-%m-%d')}")

    meta_section = "\n".join(meta_lines)

    markdown_parts = [
        f"# {paper.title}",
        "## 元数据\n" + meta_section,
        _join_section("阅读 TODO", todo),
        _join_section("关键发现", findings),
        f"## 结论\n\n{conclusion}\n",
    ]

    markdown = "\n\n".join(part for part in markdown_parts if part)

    return PaperSummary(
        arxiv_id=paper.arxiv_id,
        title=paper.title,
        topic=topic_label,
        todo=todo,
        findings=findings,
        conclusion=conclusion,
        markdown=markdown,
        score=score,
        metadata={
            "authors": paper.authors,
            "categories": paper.categories,
            "published": paper.published.isoformat() if paper.published else None,
            "generated_at": datetime.utcnow().isoformat(),
            "arxiv_url": paper.extra.get("arxiv_url"),
            "pdf_url": paper.extra.get("pdf_url"),
        },
    )
