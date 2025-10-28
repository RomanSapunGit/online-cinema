from __future__ import annotations
from typing import TYPE_CHECKING

from jinja2 import Environment, FileSystemLoader

from celery_apps.email_tasks import send_email
from notifications.interfaces import EmailSenderInterface

if TYPE_CHECKING:
    from config.settings import BaseAppSettings


class EmailSender(EmailSenderInterface):

    def __init__(
            self,
            email: str,
            template_dir: str,
            activation_email_template_name: str,
            activation_complete_email_template_name: str,
            password_email_template_name: str,
            password_complete_email_template_name: str,
            notification_email_template_name: str,
            settings: BaseAppSettings,
    ):
        self._email = email
        self._activation_email_template_name = activation_email_template_name
        self._activation_complete_email_template_name = activation_complete_email_template_name
        self._password_email_template_name = password_email_template_name
        self._password_complete_email_template_name = password_complete_email_template_name
        self._notification_template = notification_email_template_name
        self._env = Environment(loader=FileSystemLoader(template_dir))
        self._settings = settings

    async def _send_email(self, recipient: str, subject: str, html_content: str) -> None:
        send_email.delay(self._email, subject, html_content, self._settings.SENDGRID_API_KEY, recipient)

    async def send_notification_email(
            self,
            email: str,
            subject: str,
            notification_text: str,
            notification_title: str
    ) -> None:
        template = self._env.get_template(self._notification_template)
        html_content = template.render(
            email=email,
            notification_text=notification_text,
            notification_title=notification_title
        )
        await self._send_email(email, subject, html_content)

    async def send_activation_email(self, email: str, activation_link: str) -> None:
        template = self._env.get_template(self._activation_email_template_name)
        html_content = template.render(email=email, activation_link=activation_link)
        subject = "Account Activation"
        await self._send_email(email, subject, html_content)

    async def send_activation_complete_email(self, email: str, login_link: str) -> None:
        template = self._env.get_template(self._activation_complete_email_template_name)
        html_content = template.render(email=email, login_link=login_link)
        subject = "Account Activated Successfully"
        await self._send_email(email, subject, html_content)

    async def send_password_reset_email(self, email: str, reset_link: str) -> None:
        template = self._env.get_template(self._password_email_template_name)
        html_content = template.render(email=email, reset_link=reset_link)
        subject = "Password Reset Request"
        await self._send_email(email, subject, html_content)

    async def send_password_reset_complete_email(self, email: str, login_link: str) -> None:
        template = self._env.get_template(self._password_complete_email_template_name)
        html_content = template.render(email=email, login_link=login_link)
        subject = "Your Password Has Been Successfully Reset"
        await self._send_email(email, subject, html_content)
