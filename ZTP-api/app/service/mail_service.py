import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_email(to_address, subject, body, sender="bmi-service notification <bmi-notify@example.com>"):
    smtp_server = "smtp.example.com"
    smtp_port = 25
    try:
        msg = MIMEMultipart()
        msg["From"] = sender
        msg["To"] = to_address
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "html"))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.sendmail(sender, to_address, msg.as_string())
        server.quit()
        # logger.info(f"Email sent successfully to {to_address}")
    except Exception:
        to_address = to_address.replace("\r\n", "").replace("\n", "")
        logger.error(f"Failed to send email to {to_address}")
