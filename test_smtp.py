import smtplib
import os
from email.message import EmailMessage

# 读取配置（模拟 pipeline.yaml）
sender = "yerenbot@gmail.com"
username = "yerenbot@gmail.com"
password = os.environ.get("MAIL_PASSWORD", "")
smtp_host = "smtp.gmail.com"
smtp_port = 465
use_ssl = True
use_tls = False

print(f"[TEST] Sender: {sender}")
print(f"[TEST] Username: {username}")
print(f"[TEST] Password length: {len(password)}")
print(f"[TEST] SMTP: {smtp_host}:{smtp_port}, SSL={use_ssl}, TLS={use_tls}")

if not password:
    print("[ERROR] MAIL_PASSWORD environment variable not set")
    exit(1)

msg = EmailMessage()
msg["Subject"] = "Test from LLM4ArxivPaper"
msg["From"] = sender
msg["To"] = "syeren@foxmail.com"
msg.set_content("This is a test email.", subtype="plain")

try:
    connection_cls = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with connection_cls(smtp_host, smtp_port, timeout=30) as smtp:
        if use_tls and not use_ssl:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(msg)
    print("[SUCCESS] Email sent successfully!")
except Exception as exc:
    print(f"[ERROR] Failed to send: {exc}")
    import traceback
    traceback.print_exc()
