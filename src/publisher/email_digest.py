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

		# Calculate statistics
		total_topics = len(topics)
		avg_score = sum(self._format_score_value(s) for s in summaries) / total if total > 0 else 0
		
		import datetime
		update_time = datetime.datetime.now().strftime("%Y-%m-%d")

		# Modern email template with inline styles
		html = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>LLM4ArxivPaper Weekly Digest</title>
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background-color:#f5f5f5;color:#333;">
  <div style="max-width:700px;margin:0 auto;background-color:#ffffff;">
    
    <!-- Header Banner -->
    <div style="background:linear-gradient(135deg,#2563eb 0%,#1d4ed8 100%);padding:40px 30px;text-align:center;color:#ffffff;">
      <h1 style="margin:0 0 10px;font-size:28px;font-weight:700;">📚 LLM4ArxivPaper</h1>
      <p style="margin:0;font-size:16px;opacity:0.95;">Weekly Curated Research Papers</p>
    </div>
    
    <!-- Stats Cards -->
    <div style="padding:30px;background-color:#f8f9fa;">
      <div style="display:flex;gap:15px;justify-content:center;flex-wrap:wrap;">
        <div style="flex:1;min-width:150px;background:#ffffff;padding:20px;border-radius:8px;text-align:center;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
          <div style="font-size:32px;font-weight:700;color:#2563eb;margin-bottom:5px;">{total}</div>
          <div style="font-size:14px;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px;">Papers</div>
        </div>
        <div style="flex:1;min-width:150px;background:#ffffff;padding:20px;border-radius:8px;text-align:center;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
          <div style="font-size:32px;font-weight:700;color:#2563eb;margin-bottom:5px;">{total_topics}</div>
          <div style="font-size:14px;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px;">Topics</div>
        </div>
        <div style="flex:1;min-width:150px;background:#ffffff;padding:20px;border-radius:8px;text-align:center;box-shadow:0 2px 4px rgba(0,0,0,0.1);">
          <div style="font-size:32px;font-weight:700;color:#2563eb;margin-bottom:5px;">{avg_score:.1f}</div>
          <div style="font-size:14px;color:#6b7280;text-transform:uppercase;letter-spacing:0.5px;">Avg Score</div>
        </div>
      </div>
"""

		if self.site_base_url:
			html += f"""
      <div style="text-align:center;margin-top:20px;">
        <a href="{self.site_base_url}" style="display:inline-block;background:#2563eb;color:#ffffff;padding:12px 30px;border-radius:6px;text-decoration:none;font-weight:600;font-size:15px;">📖 View Full Report</a>
      </div>
"""

		html += """
    </div>
    
    <!-- Main Content -->
    <div style="padding:30px;">
"""

		# Topic sections
		for topic_label, topic_items in topics.items():
			html += f"""
      <!-- Topic Section -->
      <div style="margin-bottom:40px;">
        <div style="border-bottom:2px solid #e5e7eb;padding-bottom:10px;margin-bottom:20px;">
          <h2 style="margin:0;font-size:22px;font-weight:700;color:#111827;display:inline-block;">{topic_label}</h2>
          <span style="margin-left:10px;background:#eff6ff;color:#2563eb;padding:4px 12px;border-radius:12px;font-size:13px;font-weight:600;">{len(topic_items)} papers</span>
        </div>
"""
			
			for summary in topic_items:
				url = f"{self.site_base_url}/topics/{summary.topic.name}/{summary.paper.arxiv_id}.html" if self.site_base_url else "#"
				title = summary.paper.title
				score = self._format_score(summary)
				
				# Authors
				authors_text = ""
				if summary.paper.authors:
					author_preview = ", ".join(summary.paper.authors[:3])
					if len(summary.paper.authors) > 3:
						author_preview += " et al."
					authors_text = author_preview
				
				# Affiliations
				affiliations_text = ""
				if summary.paper.affiliations:
					aff_preview = summary.paper.affiliations[0]
					if len(summary.paper.affiliations) > 1:
						aff_preview += f" +{len(summary.paper.affiliations)-1}"
					affiliations_text = aff_preview
				
				# Brief summary
				brief_text = ""
				if summary.brief_summary:
					brief_text = self._render_brief_summary(summary.brief_summary)
					if len(brief_text) > 300:
						brief_text = brief_text[:300] + "..."
				
				html += f"""
        <!-- Paper Card -->
        <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:8px;padding:20px;margin-bottom:15px;transition:box-shadow 0.2s;">
          <h3 style="margin:0 0 12px;font-size:18px;font-weight:600;line-height:1.4;">
            <a href="{url}" style="color:#111827;text-decoration:none;">{title}</a>
          </h3>
"""
				
				if authors_text or affiliations_text:
					html += """
          <div style="margin-bottom:12px;font-size:14px;color:#6b7280;">
"""
					if authors_text:
						html += f"""
            <div style="margin-bottom:4px;">👤 {authors_text}</div>
"""
					if affiliations_text:
						html += f"""
            <div style="margin-bottom:4px;">🏛️ {affiliations_text}</div>
"""
					html += """
          </div>
"""
				
				if brief_text:
					html += f"""
          <div style="margin-bottom:12px;font-size:14px;color:#374151;line-height:1.6;">
            {brief_text}
          </div>
"""
				
				html += f"""
          <div style="display:flex;justify-content:space-between;align-items:center;padding-top:12px;border-top:1px solid #f3f4f6;">
            <span style="font-size:13px;color:#9ca3af;">📊 Relevance: <strong style="color:#2563eb;">{score}</strong></span>
            <a href="{url}" style="background:#eff6ff;color:#2563eb;padding:6px 16px;border-radius:6px;text-decoration:none;font-size:13px;font-weight:600;">View Details →</a>
          </div>
        </div>
"""

			html += """
      </div>
"""

		html += """
    </div>
    
    <!-- Footer -->
    <div style="background:#f8f9fa;padding:30px;text-align:center;border-top:1px solid #e5e7eb;">
      <div style="margin-bottom:15px;">
        <span style="font-size:24px;">📚</span>
      </div>
      <div style="font-size:14px;color:#6b7280;margin-bottom:10px;">
        <strong>LLM4ArxivPaper</strong> - Intelligent Paper Reading Assistant
      </div>
"""
		
		if self.site_base_url:
			html += f"""
      <div style="font-size:13px;color:#9ca3af;">
        <a href="{self.site_base_url}" style="color:#2563eb;text-decoration:none;">Visit Website</a>
      </div>
"""
		
		html += f"""
      <div style="font-size:12px;color:#9ca3af;margin-top:15px;">
        Updated: {update_time}
      </div>
    </div>
    
  </div>
</body>
</html>
"""

		return html

	@staticmethod
	def _format_score(summary: PaperSummary) -> str:
		total_weight = sum(score.weight for score in summary.score_details.scores) or 1.0
		value = sum(score.weight * score.value for score in summary.score_details.scores)
		return f"{(value / total_weight) * 100:.1f}"

	@staticmethod
	def _format_score_value(summary: PaperSummary) -> float:
		"""Return numeric score value for calculations."""
		total_weight = sum(score.weight for score in summary.score_details.scores) or 1.0
		value = sum(score.weight * score.value for score in summary.score_details.scores)
		return (value / total_weight) * 100

	@staticmethod
	def _render_brief_summary(summary_text: str) -> str:
		paragraphs = [p.strip() for p in summary_text.split("\n\n") if p.strip()]
		if not paragraphs:
			return summary_text.strip()
		return "<br/><br/>".join(p.replace("\n", " ") for p in paragraphs)
