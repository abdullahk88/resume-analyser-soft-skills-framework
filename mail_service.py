import smtplib
import random
import string
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config import Config


def generate_otp(length: int = 6) -> str:
    return ''.join(random.choices(string.digits, k=length))


def otp_expiry(minutes: int = 10) -> datetime:
    return datetime.now() + timedelta(minutes=minutes)


def send_otp_email(to_email: str, otp: str) -> bool:
    """Send OTP via Gmail SMTP. Falls back to console print for dev/testing."""

    # ── Dev fallback: if mail not configured, print to console ──
    if not Config.MAIL_USERNAME or not Config.MAIL_PASSWORD \
       or Config.MAIL_USERNAME == 'your_email@gmail.com':
        print("\n" + "="*50)
        print(f"[DEV MODE] OTP for {to_email}: {otp}")
        print("(Configure MAIL_USERNAME + MAIL_PASSWORD in .env for real emails)")
        print("="*50 + "\n")
        return True   # Return True so the flow continues

    subject = "Mocka AI – Password Reset Code"
    html_body = f"""
    <div style="font-family:'Segoe UI',sans-serif;max-width:480px;margin:auto;
                background:#0F172A;color:#e2e8f0;padding:40px;border-radius:12px;">
      <h2 style="color:#14B8A6;margin-bottom:4px;font-size:24px;">Mocka AI</h2>
      <p style="color:#94a3b8;font-size:13px;margin-top:0;">AI-Powered Interview Preparation</p>
      <hr style="border:1px solid #1e293b;margin:24px 0;">
      <p style="font-size:15px;">Your password reset code:</p>
      <div style="background:#1e293b;border:1px solid #334155;border-radius:10px;
                  text-align:center;padding:28px;margin:20px 0;">
        <span style="font-size:38px;font-weight:800;letter-spacing:14px;
                     color:#14B8A6;font-family:monospace;">{otp}</span>
      </div>
      <p style="color:#94a3b8;font-size:13px;">
        Expires in <strong style="color:#e2e8f0;">10 minutes</strong>.
        Ignore if you didn't request this.
      </p>
      <hr style="border:1px solid #1e293b;margin:24px 0;">
      <p style="color:#64748b;font-size:12px;">Mocka AI &nbsp;•&nbsp; Powered by Groq &amp; LLaMA</p>
    </div>
    """

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From']    = Config.MAIL_USERNAME
    msg['To']      = to_email
    msg.attach(MIMEText(html_body, 'html'))

    try:
        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.sendmail(Config.MAIL_USERNAME, to_email, msg.as_string())
        print(f"[MAIL] OTP sent to {to_email}")
        return True
    except smtplib.SMTPAuthenticationError:
        print("[MAIL] AUTH FAILED — use a Gmail App Password, not your real Gmail password.")
        print(f"[MAIL] Fallback OTP for {to_email}: {otp}")
        return True   # Still let user continue via console OTP
    except Exception as e:
        print(f"[MAIL] Failed: {e}")
        print(f"[MAIL] Fallback OTP for {to_email}: {otp}")
        return True   # Fallback so dev can still test