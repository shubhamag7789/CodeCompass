from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_recovery_code(email: str, code: str) -> None:
    """Dispatches a password reset recovery code via SMTP email, or securely logs to server console in local mode."""
    smtp_host = os.getenv("SMTP_HOST", "").strip()
    smtp_port = int(os.getenv("SMTP_PORT", "587").strip() or "587")
    smtp_user = os.getenv("SMTP_USER", "").strip()
    smtp_pass = os.getenv("SMTP_PASSWORD", "").strip()
    smtp_from = os.getenv("SMTP_FROM", "CodeCompass Security <security@codecompass.dev>").strip()
    use_tls = os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")

    # If SMTP is configured, send real email
    if smtp_host and smtp_user and smtp_pass:
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = "CodeCompass - Password Reset Code"
            msg["From"] = smtp_from
            msg["To"] = email

            text_content = f"""Hello,

You requested a password reset for your CodeCompass account.

Your 6-digit recovery code is: {code}

This code will expire in 15 minutes. If you did not request this, please disregard this email.
"""

            html_content = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 500px; margin: 0 auto; padding: 24px; background-color: #0c101d; color: #f8fafc; border-radius: 12px; border: 1px solid #1e293b;">
                <h2 style="color: #38bdf8; margin-bottom: 8px;">CodeCompass Security</h2>
                <p style="color: #94a3b8; font-size: 14px;">You requested a password reset for your account (<strong>{email}</strong>).</p>
                <div style="background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 8px; padding: 16px; text-align: center; margin: 20px 0;">
                    <span style="font-family: monospace; font-size: 28px; font-weight: bold; letter-spacing: 6px; color: #38bdf8;">{code}</span>
                </div>
                <p style="color: #64748b; font-size: 12px;">This verification code is single-use and expires in 15 minutes.<br>If you did not request this, you can safely ignore this email.</p>
            </div>
            """

            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(smtp_host, smtp_port, timeout=10.0) as server:
                if use_tls:
                    server.starttls()
                server.login(smtp_user, smtp_pass)
                server.sendmail(smtp_from, [email], msg.as_string())
            return
        except Exception as exc:
            # Fall back to secure server console output if SMTP fails
            print(f"[SECURITY WARNING] Failed to send email via SMTP ({exc}). Logging code to server console.")

    # Local mode fallback: strictly printed to the host server console, NEVER returned over HTTP
    try:
        print(f"\n==================== [CODECOMPASS SECURITY] ====================", flush=True)
        print(f"Password reset requested for: {email}", flush=True)
        print(f"One-Time Recovery Code:      {code}", flush=True)
        print(f"Expires in:                  15 minutes", flush=True)
        print(f"================================================================\n", flush=True)
    except Exception:
        pass
