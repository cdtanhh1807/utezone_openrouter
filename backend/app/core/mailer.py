import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
import re

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SMTP_EMAIL", "")
SENDER_PASSWORD = os.getenv("SMTP_PASS", "")

# ========== TEMPLATES ==========

OTP_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Segoe UI,Tahoma,Geneva,Verdana,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f0f2f5;padding:40px 0;">
<tr><td align="center">
<table width="480" cellpadding="0" cellspacing="0" border="0" style="background:#fff;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.08);overflow:hidden;">
<tr><td style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:28px 32px;text-align:center;">
<h1 style="color:#fff;margin:0;font-size:22px;font-weight:700;letter-spacing:1px;">UTEZone</h1>
</td></tr>
<tr><td style="padding:36px 32px;">
<h2 style="color:#1a1a2e;margin:0 0 14px 0;font-size:18px;font-weight:600;">{title}</h2>
<p style="color:#4a5568;font-size:14px;line-height:1.6;margin:0 0 20px 0;">
Chào {user_name},<br>
{description}
</p>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:20px 0;"><tr><td align="center">
<div style="display:inline-block;background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);border-radius:10px;padding:3px;">
<div style="background:#fff;border-radius:8px;padding:16px 36px;">
<p style="margin:0 0 6px 0;color:#718096;font-size:11px;text-transform:uppercase;letter-spacing:2px;">Mã xác thực</p>
<p style="margin:0;font-size:32px;font-weight:800;color:#1a1a2e;letter-spacing:6px;font-family:Courier New,monospace;">{otp}</p>
</div></div>
</td></tr></table>
<p style="color:#4a5568;font-size:13px;line-height:1.6;margin:16px 0 0 0;text-align:center;">
Mã OTP này sẽ <strong style="color:#e53e3e;">hết hạn sau {expiry} phút</strong>.
</p>
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin:24px 0;"><tr><td style="border-top:1px solid #e2e8f0;"></td></tr></table>
<p style="color:#718096;font-size:12px;line-height:1.6;margin:0;">
<strong style="color:#e53e3e;">⚠️ Lưu ý:</strong> Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email này. Đừng chia sẻ mã OTP với bất kỳ ai.
</p>
</td></tr>
<tr><td style="background:#f7fafc;padding:20px 32px;text-align:center;border-top:1px solid #e2e8f0;">
<p style="color:#a0aec0;font-size:11px;margin:0;">© 2026 UTEZone</p>
</td></tr>
</table></td></tr></table></body></html>"""

CHANNEL_TEMPLATE = """<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f0f2f5;font-family:Segoe UI,Tahoma,Geneva,Verdana,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f0f2f5;padding:40px 0;">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" border="0" style="background:#fff;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.08);overflow:hidden;">
<tr><td style="background:linear-gradient(135deg,#667eea 0%,#764ba2 100%);padding:24px 32px;text-align:center;">
<h1 style="color:#fff;margin:0;font-size:20px;font-weight:700;letter-spacing:1px;">UTEZone Meet</h1>
</td></tr>
<tr><td style="padding:32px;">
<div style="color:#1a1a2e;font-size:15px;line-height:1.7;">
{body}
</div>
</td></tr>
<tr><td style="background:#f7fafc;padding:20px 32px;text-align:center;border-top:1px solid #e2e8f0;">
<p style="color:#a0aec0;font-size:11px;margin:0;">© 2026 UTEZone</p>
</td></tr>
</table></td></tr></table></body></html>"""


def _extract_otp(text: str) -> str | None:
    match = re.search(r'(?:OTP|otp|code|mã)[^\d]*(\d{4,8})', text)
    return match.group(1) if match else None


def _is_otp_email(subject: str, body: str) -> bool:
    subject_lower = subject.lower()
    body_lower = body.lower()
    return (
        "otp" in subject_lower or "xác thực" in subject_lower or "mã" in subject_lower
    ) and _extract_otp(body) is not None


def _build_otp_html(subject: str, body: str, from_email: str) -> tuple[str, str]:
    otp = _extract_otp(body)
    if not otp:
        return body, None

    subject_lower = subject.lower()
    if "đăng ký" in subject_lower or "đăng kí" in subject_lower or "register" in subject_lower:
        title = "Xác thực đăng ký tài khoản"
        description = "Bạn vừa yêu cầu đăng ký tài khoản tại UTEZone. Vui lòng sử dụng mã OTP dưới đây để hoàn tất xác thực:"
    elif "mật khẩu" in subject_lower or "password" in subject_lower or "quên" in subject_lower:
        title = "Xác thực thay đổi mật khẩu"
        description = "Bạn vừa yêu cầu thay đổi mật khẩu tại UTEZone. Vui lòng sử dụng mã OTP dưới đây để xác thực:"
    else:
        title = "Xác thực tài khoản"
        description = "Vui lòng sử dụng mã OTP dưới đây để xác thực:"

    html = OTP_TEMPLATE.format(
        title=title,
        user_name="bạn",
        description=description,
        otp=otp,
        expiry=3
    )
    return body, html


def _build_channel_html(body: str) -> str:
    body_html = body.replace("\n", "<br>").replace("\r", "")
    return CHANNEL_TEMPLATE.format(body=body_html)


async def send_email(from_email: str, to_email: str, subject: str, body: str):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise RuntimeError("Thiếu SMTP_EMAIL hoặc SMTP_PASS")

    text_body = body
    html_body = None

    if _is_otp_email(subject, body):
        text_body, html_body = _build_otp_html(subject, body, from_email)
    elif from_email == "UTEZone Meet" or "UTEZone Meet" in from_email:
        html_body = _build_channel_html(body)

    if html_body:
        message = MIMEMultipart("alternative")
        message.attach(MIMEText(text_body, "plain", "utf-8"))
        message.attach(MIMEText(html_body, "html", "utf-8"))
    else:
        message = MIMEMultipart()
        message.attach(MIMEText(body, "plain", "utf-8"))

    message["From"] = f"{from_email} <{SENDER_EMAIL}>"
    message["To"] = to_email
    message["Subject"] = subject

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, message.as_string())
        print(f"✅ Email sent to {to_email}")
    except Exception as e:
        print(f"❌ Failed to send email: {e}")
        raise