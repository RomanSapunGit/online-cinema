from celery import shared_task
from sendgrid import SendGridAPIClient, Mail

from exceptions import BaseEmailError


@shared_task
def send_email(email: str, subject: str, html_content: str, api_key: str, recipient: str):
    message = Mail(
        from_email=email,
        to_emails=recipient,
        subject=subject,
        html_content=html_content
    )
    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        if 202 != response.status_code:
            raise BaseEmailError(f"Failed to send email to {recipient}: {response.headers}")
    except Exception as e:
        raise BaseEmailError(f"Failed to send email to {recipient}: {e}")
