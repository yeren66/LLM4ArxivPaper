"""Optional email digest sender.

Builds a single HTML email summarising the papers a pipeline run kept. The
HTML is deliberately table-based with inline styles only — that is the one
layout approach that renders consistently across Gmail, Apple Mail and
Outlook (Outlook ignores flexbox and most modern CSS).

Chrome strings respect ``language`` so a zh-CN instance gets a Chinese frame
around its Chinese analyses, and an English instance an English one.
"""

from __future__ import annotations

import datetime
import html
import re
import smtplib
from email.message import EmailMessage
from typing import Iterable

from core.models import EmailConfig, PaperSummary


# --- email chrome i18n -------------------------------------------------------
# Only the email's own labels live here. Paper content (titles, summaries) is
# whatever language the pipeline produced it in.

_STRINGS = {
	# Default subject line. Used when email.subject_template is left empty in
	# the config, so the subject follows openai.language like the body does.
	"subject": {
		"zh-CN": "LLM4ArxivPaper 周报 - {run_date}（{paper_count} 篇）",
		"en": "LLM4ArxivPaper Weekly - {run_date} ({paper_count} papers)",
	},
	"subtitle": {"zh-CN": "本周精选论文", "en": "Weekly Curated Research Papers"},
	"stat_papers": {"zh-CN": "篇论文", "en": "Papers"},
	"stat_topics": {"zh-CN": "个方向", "en": "Topics"},
	"stat_avg": {"zh-CN": "平均相关度", "en": "Avg Score"},
	"view_report": {"zh-CN": "查看完整报告", "en": "View Full Report"},
	"papers_badge": {"zh-CN": "{n} 篇", "en": "{n} papers"},
	"why_matters": {"zh-CN": "为什么值得读", "en": "Why it matters"},
	"relevance": {"zh-CN": "相关度", "en": "Relevance"},
	"view_details": {"zh-CN": "查看详情", "en": "View details"},
	"footer_tagline": {
		"zh-CN": "智能 arXiv 论文阅读助手",
		"en": "Intelligent arXiv reading assistant",
	},
	"visit_site": {"zh-CN": "访问网站", "en": "Visit website"},
	"updated": {"zh-CN": "更新于", "en": "Updated"},
	"empty": {
		"zh-CN": "本周没有论文达到相关度阈值，因此没有可推送的分析。",
		"en": "No papers cleared the relevance threshold this week, so there is nothing to digest.",
	},
}


class EmailDigest:
	def __init__(
		self,
		email_config: EmailConfig,
		site_base_url: str,
		language: str = "zh-CN",
	):
		self.email_config = email_config
		self.site_base_url = site_base_url.rstrip("/")
		# Normalise to one of the two supported chrome languages.
		self.language = "en" if str(language).lower().startswith("en") else "zh-CN"

	def _t(self, key: str, **kwargs: object) -> str:
		"""Look up an email-chrome string in the configured language."""
		entry = _STRINGS.get(key, {})
		text = entry.get(self.language) or entry.get("zh-CN") or key
		return text.format(**kwargs) if kwargs else text

	def _content(self, summary: PaperSummary, field: str) -> str:
		"""A paper's text field in this instance's language.

		Analysis is generated in English and held on the dataclass as such;
		``summary.translations`` carries the translated mirror. An English
		instance always gets the English text.
		"""
		english = getattr(summary, field, "") or ""
		if self.language == "en":
			return english
		translated = (summary.translations or {}).get(field)
		return translated or english

	# ------------------------------------------------------------------

	def send(self, summaries: Iterable[PaperSummary], subject_context: dict) -> None:
		config = self.email_config
		if not config.enabled:
			print("[INFO] Email digest disabled; skipping send step.")
			return
		if not config.sender or not config.recipients:
			print("[WARN] Email sender/recipients not configured; skip sending.")
			return
		if not config.smtp_host:
			print("[WARN] SMTP host not configured; skip sending.")
			return

		recipient_list = list(config.recipients)
		if not recipient_list:
			print("[WARN] No email recipients provided; skip sending.")
			return

		required_auth = config.username or config.password
		if required_auth and not (config.username and config.password):
			print("[WARN] SMTP credentials incomplete (username/password); skip sending.")
			return

		body = self._build_body(list(summaries), subject_context)
		# An empty subject_template means "follow the configured language",
		# matching the body. A non-empty one is the user's explicit override.
		template = config.subject_template.strip() or self._t("subject")
		subject = template.format(**subject_context)

		message = EmailMessage()
		message["Subject"] = subject
		message["From"] = config.sender
		message["To"] = ", ".join(recipient_list)
		message.set_content(body, subtype="html", charset="utf-8")

		connection_cls = smtplib.SMTP_SSL if config.use_ssl else smtplib.SMTP
		try:
			with connection_cls(config.smtp_host, config.smtp_port, timeout=config.timeout) as smtp:
				if config.use_tls and not config.use_ssl:
					smtp.starttls()
				if config.username and config.password:
					smtp.login(config.username, config.password)
				smtp.send_message(message)
			print(f"[INFO] Email digest sent to {len(recipient_list)} recipient(s).")
		except Exception as exc:  # pragma: no cover - runtime environment specific
			print(f"[WARN] Failed to send email digest: {exc}")

	# ------------------------------------------------------------------

	def _build_body(self, summaries: list[PaperSummary], subject_context: dict) -> str:
		total = len(summaries)
		update_time = datetime.datetime.now().strftime("%Y-%m-%d")

		header = self._render_header()
		footer = self._render_footer(update_time)

		if total == 0:
			content = f"""
    <tr><td style="padding:48px 30px;text-align:center;color:#6b7280;font-size:15px;line-height:1.6;">
      {html.escape(self._t("empty"))}
    </td></tr>
"""
			return self._wrap(header + content + footer)

		topics: dict[str, list[PaperSummary]] = {}
		for summary in summaries:
			topics.setdefault(summary.topic.label, []).append(summary)

		avg_score = sum(self._score_value(s) for s in summaries) / total

		stats = self._render_stats(total, len(topics), avg_score)

		sections = ""
		for topic_label, topic_items in topics.items():
			sections += self._render_topic(topic_label, topic_items)

		content = f"""
    <tr><td style="padding:30px;">
      {sections}
    </td></tr>
"""
		return self._wrap(header + stats + content + footer)

	# ------------------------------------------------------------------
	# Section renderers. Everything is <table>-based: Outlook's rendering
	# engine ignores flexbox, so flex layouts collapse into a single column.

	@staticmethod
	def _wrap(inner: str) -> str:
		return f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LLM4ArxivPaper</title>
</head>
<body style="margin:0;padding:0;background-color:#f5f5f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;color:#333;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f5f5f5;">
    <tr><td align="center" style="padding:0;">
      <table role="presentation" width="700" cellpadding="0" cellspacing="0" style="max-width:700px;width:100%;background-color:#ffffff;">
{inner}
      </table>
    </td></tr>
  </table>
</body>
</html>
"""

	def _render_header(self) -> str:
		return f"""
    <tr><td style="background:linear-gradient(135deg,#2563eb 0%,#1d4ed8 100%);padding:36px 30px;text-align:center;">
      <div style="margin:0 0 6px;font-size:26px;font-weight:700;color:#ffffff;">LLM4ArxivPaper</div>
      <div style="margin:0;font-size:15px;color:#dbeafe;">{html.escape(self._t("subtitle"))}</div>
    </td></tr>
"""

	def _render_stats(self, total: int, topic_count: int, avg_score: float) -> str:
		def cell(value: str, label: str) -> str:
			return f"""
          <td width="33%" style="padding:6px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;border:1px solid #e5e7eb;">
              <tr><td style="padding:18px;text-align:center;">
                <div style="font-size:28px;font-weight:700;color:#2563eb;">{value}</div>
                <div style="font-size:13px;color:#6b7280;margin-top:4px;">{html.escape(label)}</div>
              </td></tr>
            </table>
          </td>
"""

		button = ""
		if self.site_base_url:
			button = f"""
      <tr><td style="text-align:center;padding-top:18px;">
        <a href="{html.escape(self.site_base_url)}" style="display:inline-block;background:#2563eb;color:#ffffff;padding:11px 28px;border-radius:6px;text-decoration:none;font-weight:600;font-size:14px;">{html.escape(self._t("view_report"))}</a>
      </td></tr>
"""

		return f"""
    <tr><td style="padding:24px 24px 6px;background-color:#f8f9fa;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
        <tr>
          {cell(str(total), self._t("stat_papers"))}
          {cell(str(topic_count), self._t("stat_topics"))}
          {cell(f"{avg_score:.1f}", self._t("stat_avg"))}
        </tr>
      </table>
      {button}
    </td></tr>
    <tr><td style="height:6px;background-color:#f8f9fa;line-height:6px;">&nbsp;</td></tr>
"""

	def _render_topic(self, topic_label: str, items: list[PaperSummary]) -> str:
		badge = self._t("papers_badge", n=len(items))
		cards = "".join(self._render_card(s) for s in items)
		return f"""
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:28px;">
        <tr><td style="border-bottom:2px solid #e5e7eb;padding-bottom:8px;">
          <span style="font-size:20px;font-weight:700;color:#111827;">{html.escape(topic_label)}</span>
          <span style="margin-left:8px;background:#eff6ff;color:#2563eb;padding:3px 10px;border-radius:10px;font-size:12px;font-weight:600;">{html.escape(badge)}</span>
        </td></tr>
        <tr><td style="height:14px;line-height:14px;">&nbsp;</td></tr>
        <tr><td>{cards}</td></tr>
      </table>
"""

	def _render_card(self, summary: PaperSummary) -> str:
		paper = summary.paper
		url = (
			f"{self.site_base_url}/papers/{paper.arxiv_id}"
			if self.site_base_url
			else (paper.arxiv_url or "#")
		)
		url = html.escape(url)
		title = html.escape(paper.title or paper.arxiv_id)
		score = f"{self._score_value(summary):.1f}"

		# Authors + affiliations, one muted line.
		meta_bits: list[str] = []
		if paper.authors:
			authors = ", ".join(paper.authors[:3])
			if len(paper.authors) > 3:
				authors += " et al."
			meta_bits.append(authors)
		if paper.affiliations:
			aff = paper.affiliations[0]
			if len(paper.affiliations) > 1:
				aff += f" +{len(paper.affiliations) - 1}"
			meta_bits.append(aff)
		meta_line = ""
		if meta_bits:
			meta_line = f"""
          <tr><td style="padding-bottom:10px;font-size:13px;color:#6b7280;">{html.escape(" · ".join(meta_bits))}</td></tr>
"""

		# Relevance note — the triage line: why THIS paper matters to the
		# reader. Shown as an accented block above the descriptive summary.
		relevance_block = ""
		rel = self._content(summary, "relevance").strip()
		if rel:
			relevance_block = f"""
          <tr><td style="padding-bottom:10px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;border-left:3px solid #2563eb;">
              <tr><td style="padding:10px 12px;">
                <div style="font-size:11px;font-weight:700;color:#2563eb;text-transform:uppercase;letter-spacing:0.4px;margin-bottom:3px;">{html.escape(self._t("why_matters"))}</div>
                <div style="font-size:13px;color:#374151;line-height:1.6;">{self._render_text(rel, limit=320)}</div>
              </td></tr>
            </table>
          </td></tr>
"""

		# Descriptive brief summary.
		brief_block = ""
		brief = self._content(summary, "brief_summary")
		if brief:
			brief_block = f"""
          <tr><td style="padding-bottom:12px;font-size:13px;color:#4b5563;line-height:1.7;">{self._render_text(brief, limit=300)}</td></tr>
"""

		footer = f"""
          <tr><td style="border-top:1px solid #f3f4f6;padding-top:10px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr>
                <td style="font-size:12px;color:#9ca3af;">{html.escape(self._t("relevance"))}: <strong style="color:#2563eb;">{score}</strong></td>
                <td align="right"><a href="{url}" style="background:#eff6ff;color:#2563eb;padding:5px 14px;border-radius:6px;text-decoration:none;font-size:12px;font-weight:600;">{html.escape(self._t("view_details"))}</a></td>
              </tr>
            </table>
          </td></tr>
"""

		return f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border:1px solid #e5e7eb;border-radius:8px;margin-bottom:14px;">
          <tr><td style="padding:18px;">
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
              <tr><td style="padding-bottom:8px;font-size:16px;font-weight:600;line-height:1.4;">
                <a href="{url}" style="color:#111827;text-decoration:none;">{title}</a>
              </td></tr>
              {meta_line}
              {relevance_block}
              {brief_block}
              {footer}
            </table>
          </td></tr>
        </table>
"""

	def _render_footer(self, update_time: str) -> str:
		site_link = ""
		if self.site_base_url:
			site_link = f"""
      <div style="font-size:13px;margin-bottom:10px;">
        <a href="{html.escape(self.site_base_url)}" style="color:#2563eb;text-decoration:none;">{html.escape(self._t("visit_site"))}</a>
      </div>
"""
		return f"""
    <tr><td style="background:#f8f9fa;padding:26px 30px;text-align:center;border-top:1px solid #e5e7eb;">
      <div style="font-size:14px;color:#6b7280;margin-bottom:6px;"><strong>LLM4ArxivPaper</strong></div>
      <div style="font-size:13px;color:#9ca3af;margin-bottom:10px;">{html.escape(self._t("footer_tagline"))}</div>
      {site_link}
      <div style="font-size:12px;color:#9ca3af;">{html.escape(self._t("updated"))} {update_time}</div>
    </td></tr>
"""

	# ------------------------------------------------------------------
	# Helpers

	@staticmethod
	def _score_value(summary: PaperSummary) -> float:
		"""Weighted relevance score, normalised to 0-100."""
		scores = summary.score_details.scores
		total_weight = sum(s.weight for s in scores) or 1.0
		value = sum(s.weight * s.value for s in scores)
		return (value / total_weight) * 100

	@staticmethod
	def _render_text(text: str, limit: int) -> str:
		"""Truncate plain text to ``limit`` chars, THEN HTML-escape and turn
		paragraph breaks into <br/>.

		Order matters: escaping has to happen after truncation (so the cut
		never lands inside an entity) and before the <br/> tags are inserted
		(so the tags survive).
		"""
		plain = (text or "").strip()
		if len(plain) > limit:
			plain = plain[:limit].rstrip() + "…"
		paragraphs = [p.strip() for p in plain.split("\n\n") if p.strip()]
		if not paragraphs:
			return html.escape(plain)
		escaped = [html.escape(re.sub(r"\s*\n\s*", " ", p)) for p in paragraphs]
		return "<br/><br/>".join(escaped)
