import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("SMTP_EMAIL", "")
SENDER_PASSWORD = os.getenv("SMTP_PASS", "")

async def send_email(from_email: str, to_email: str, subject: str, body: str):
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        raise RuntimeError("Thiếu SMTP_EMAIL hoặc SMTP_PASS")
    
    message = MIMEMultipart()
    message["From"] = from_email 
    message["To"] = to_email
    message["Subject"] = subject

    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, message.as_string())
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")
