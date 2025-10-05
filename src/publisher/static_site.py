"""Build a minimal static site to browse paper summaries."""

from __future__ import annotations

from datetime import datetime
from html import escape
from pathlib import Path
from typing import Iterable

from core.config_loader import SiteConfig
from core.models import PaperSummary


def _render_summary(summary: PaperSummary) -> str:
    arxiv_url = summary.metadata.get("arxiv_url")
    if not arxiv_url:
        extra = summary.metadata.get("extra")
        if isinstance(extra, dict):
            arxiv_url = extra.get("arxiv_url")

    title = escape(summary.title)
    todo_items = "".join(f"<li>{escape(item)}</li>" for item in summary.todo)
    findings = "".join(f"<li>{escape(item)}</li>" for item in summary.findings)
    conclusion = escape(summary.conclusion)

    meta_parts = [f"<span class='topic'>{escape(summary.topic)}</span>"]
    if summary.score is not None:
        meta_parts.append(f"<span class='score'>相关性：{summary.score:.1f}</span>")
    published = summary.metadata.get("published")
    if published:
        meta_parts.append(f"<span class='published'>发表：{escape(str(published))}</span>")
    if arxiv_url:
        meta_parts.append(
            f"<a href='{escape(str(arxiv_url))}' target='_blank' rel='noopener noreferrer'>arXiv</a>"
        )

    meta_html = " | ".join(meta_parts)

    return (
        "<article class='paper'>"
        f"<h2>{title}</h2>"
        f"<div class='meta'>{meta_html}</div>"
        "<section><h3>阅读 TODO</h3><ul>" + todo_items + "</ul></section>"
        "<section><h3>关键发现</h3><ul>" + findings + "</ul></section>"
        f"<section><h3>结论</h3><p>{conclusion}</p></section>"
        "</article>"
    )


def build_site(config: SiteConfig, summaries: Iterable[PaperSummary]) -> Path:
    """Generate ``index.html`` under the configured output directory."""

    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    index_path = output_dir / "index.html"

    rendered = "\n".join(_render_summary(summary) for summary in summaries)

    html = f"""<!DOCTYPE html>
<html lang=\"{escape(config.locale)}\">
  <head>
    <meta charset=\"utf-8\" />
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
    <title>LLM4Reading 摘要汇总</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, \"PingFang SC\", sans-serif; margin: 2rem; background: #f8f9fa; color: #212529; }}
      header {{ margin-bottom: 2rem; }}
      .paper {{ background: #fff; padding: 1.5rem; border-radius: 12px; box-shadow: 0 8px 16px rgba(0,0,0,0.05); margin-bottom: 1.5rem; }}
      .paper h2 {{ margin-top: 0; }}
      .meta {{ font-size: 0.9rem; color: #495057; margin-bottom: 1rem; display: flex; flex-wrap: wrap; gap: 0.75rem; }}
      section {{ margin-bottom: 1rem; }}
      ul {{ padding-left: 1.2rem; }}
    </style>
  </head>
  <body>
    <header>
      <h1>LLM4Reading 摘要汇总</h1>
      <p>构建时间：{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
      <p>站点地址：{escape(config.base_url or '尚未配置')}</p>
    </header>
    {rendered or '<p>本次运行未筛选出符合条件的论文。</p>'}
  </body>
</html>
"""

    index_path.write_text(html, encoding="utf-8")
    return index_path
