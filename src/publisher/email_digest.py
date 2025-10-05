def send_digest(summaries: Iterable[PaperSummary]) -> None:
"""Minimal email digest sender."""

from __future__ import annotations

from datetime import datetime
import smtplib
from email.message import EmailMessage
from typing import Iterable

from core.config_loader import EmailConfig
from core.models import PaperSummary


def _build_body(summaries: Iterable[PaperSummary]) -> str:
    lines = ["LLM4Reading 摘要精选", ""]
    for summary in summaries:
        lines.extend(
            [
                f"标题：{summary.title}",
                f"主题：{summary.topic}",
                f"结论：{summary.conclusion}",
                "TODO：",
            ]
        )
        for item in summary.todo:
            lines.append(f"  - {item}")
        lines.append("")
    return "\n".join(lines)


def send_digest(config: EmailConfig, summaries: Iterable[PaperSummary]) -> None:
    """Send email digest if configured; silently no-op otherwise."""

    if not config.enabled:
        return

    summaries = list(summaries)
    if not summaries:
        return

    if not config.sender or not config.sender_password or not config.recipients:
        raise ValueError("Email configuration incomplete: sender, password, and recipients required when enabled")

    subject = config.subject_template.format(run_date=datetime.utcnow().strftime("%Y-%m-%d"))
    body = _build_body(summaries)

    message = EmailMessage()
    message["From"] = config.sender
    message["To"] = ", ".join(config.recipients)
    message["Subject"] = subject
    message.set_content(body)

    smtp_cls = smtplib.SMTP_SSL if not config.use_tls and config.smtp_port == 465 else smtplib.SMTP

    with smtp_cls(config.smtp_host, config.smtp_port, timeout=30) as smtp:
        if config.use_tls and smtp_cls is smtplib.SMTP:
            smtp.starttls()
        smtp.login(config.sender, config.sender_password)
        smtp.send_message(message)
