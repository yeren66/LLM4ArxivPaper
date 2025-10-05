"""Optional email digest sender."""

from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import Iterable

from core.models import EmailConfig, PaperSummary


class EmailDigest:
	def __init__(self, email_config: EmailConfig, site_base_url: str):
		self.email_config = email_config
		self.site_base_url = site_base_url.rstrip("/")

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

		# Debug: check if password was actually loaded
		if config.password:
			print(f"[DEBUG] Password loaded, length: {len(config.password)}")
		else:
			print("[WARN] Password is empty or not loaded from environment")

		body = self._build_body(list(summaries), subject_context)
		subject = config.subject_template.format(**subject_context)

		message = EmailMessage()
		message["Subject"] = subject
		message["From"] = config.sender
		message["To"] = ", ".join(recipient_list)
		message.set_content(body, subtype="html", charset="utf-8")

		connection_cls = smtplib.SMTP_SSL if config.use_ssl else smtplib.SMTP
		print(f"[DEBUG] Using {connection_cls.__name__} to connect to {config.smtp_host}:{config.smtp_port}")
		try:
			with connection_cls(config.smtp_host, config.smtp_port, timeout=config.timeout) as smtp:
				print(f"[DEBUG] Connection established, server: {smtp.sock.getpeername() if hasattr(smtp, 'sock') and smtp.sock else 'unknown'}")
				if config.use_tls and not config.use_ssl:
					print("[DEBUG] Initiating STARTTLS...")
					smtp.starttls()
				if config.username and config.password:
					print(f"[DEBUG] Logging in as {config.username}...")
					smtp.login(config.username, config.password)
					print("[DEBUG] Login successful")
				smtp.send_message(message)
			print("[INFO] Email digest submitted to SMTP server.")
		except Exception as exc:  # pragma: no cover - runtime environment specific
			print(f"[WARN] Failed to send email digest: {exc}")
			import traceback
			traceback.print_exc()

	# ------------------------------------------------------------------

	def _build_body(self, summaries: list[PaperSummary], subject_context: dict) -> str:
		total = len(summaries)
		topics: dict[str, list[PaperSummary]] = {}
		for summary in summaries:
			topics.setdefault(summary.topic.label, []).append(summary)

		lines = [
			"<h1>LLM4ArxivPaper 每周速览</h1>",
			f"<p>本次共筛选出 <strong>{total}</strong> 篇相关论文。</p>",
		]

		if self.site_base_url:
			lines.append(
				f"<p>完整详情请访问：<a href='{self.site_base_url}'>{self.site_base_url}</a></p>"
			)

		for topic_label, topic_items in topics.items():
			lines.append(f"<h2>{topic_label}（{len(topic_items)}）</h2>")
			lines.append("<ul>")
			for summary in topic_items:
				url = f"{self.site_base_url}/topics/{summary.topic.name}/{summary.paper.arxiv_id}.html" if self.site_base_url else "#"
				lines.append(
					f"  <li><a href='{url}'>{summary.paper.title}</a> — Score {self._format_score(summary)}</li>"
				)
			lines.append("</ul>")

		return "\n".join(lines)

	@staticmethod
	def _format_score(summary: PaperSummary) -> str:
		total_weight = sum(score.weight for score in summary.score_details.scores) or 1.0
		value = sum(score.weight * score.value for score in summary.score_details.scores)
		return f"{(value / total_weight) * 100:.1f}"
