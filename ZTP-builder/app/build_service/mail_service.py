import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from jinja2 import Template

logger = logging.getLogger(__name__)


def sendMail(build_event):
    toaddr = build_event["requestor"]["requestor_mail"]
    sender = "bmi-service notification <bmi-notify@example.com>"
    logger.info(f"Sending email To: {toaddr} From: {sender}")
    body = Template(
        """
        <!DOCTYPE html>
        <html>
          <body>
          <pre><b>status: </b>{{status}}</pre>
          <pre><b>status_detail: </b>{{status_detail}}</pre>
          <pre><b>build_id: </b>{{build_id}}</pre>
          <pre><b>build_type: </b>{{build_type}}</pre>
          <pre><b>host: </b>{{host}}</pre>
          <pre><b>requestor: </b>{{requestor}}</pre>
          <pre><b>logfile: </b>{{logfile}}</pre>
          </body>
        </html>
        """
    )
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = toaddr
    msg["Subject"] = f"build status for {build_event['host']} build type {build_event['build_type']}"
    html = body.render(
        status=build_event["status"],
        status_detail=build_event["status_detail"],
        build_id=build_event["build_id"],
        build_type=build_event["build_type"],
        host=build_event["host"],
        requestor=build_event["requestor"]["requestor_id"],
        logfile=build_event["metadata"].get("logfile", "null"),
    )
    # Create a MIME text object using the rendered html template
    HTML_BODY = MIMEText(html, "html")
    msg.attach(HTML_BODY)
    server = smtplib.SMTP("smtp.example.com", 25)
    text = msg.as_string()
    if build_event["status"] == "ERROR":
        logger.info("sending email to support@example.com")
        server.sendmail(sender, "support@example.com", text)
    if toaddr is None:
        logger.info("Warning: No email associated to this requestor")
        return
    logger.info(f"sending email to {toaddr}")
    server.sendmail(sender, toaddr, text)
    server.quit()
