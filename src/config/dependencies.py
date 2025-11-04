import os

from fastapi import Depends, Request
from fastapi_csrf_protect import CsrfProtect

from config.settings import BaseAppSettings, TestingSettings, Settings
from notifications.interfaces import EmailSenderInterface
from notifications.email import EmailSender
from security.interfaces import JWTAuthManagerInterface
from security.token_manager import JWTAuthManager


def get_settings() -> BaseAppSettings:
    environment = os.getenv("ENVIRONMENT", "developing")
    if environment == "testing":
        return TestingSettings()
    return Settings()


def get_accounts_email_notificator(
    settings: BaseAppSettings = Depends(get_settings)
) -> EmailSenderInterface:

    return EmailSender(
        email=settings.EMAIL_SENDER,
        template_dir=settings.PATH_TO_EMAIL_TEMPLATES_DIR,
        activation_email_template_name=settings.ACTIVATION_EMAIL_TEMPLATE_NAME,
        activation_complete_email_template_name=settings.ACTIVATION_COMPLETE_EMAIL_TEMPLATE_NAME,
        password_email_template_name=settings.PASSWORD_RESET_TEMPLATE_NAME,
        password_complete_email_template_name=settings.PASSWORD_RESET_COMPLETE_TEMPLATE_NAME,
        notification_email_template_name=settings.NOTIFICATION_EMAIL_TEMPLATE_NAME,
        settings=settings
    )


def get_jwt_auth_manager(settings: TestingSettings = Depends(get_settings)) -> JWTAuthManagerInterface:
    return JWTAuthManager(
        secret_key_access=settings.SECRET_KEY_ACCESS,
        secret_key_refresh=settings.SECRET_KEY_REFRESH,
        algorithm=settings.JWT_SIGNING_ALGORITHM
    )


async def csrf_guard(request: Request, csrf_protect: CsrfProtect = Depends()):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    
    endpoint = request.scope.get("endpoint")
    if getattr(endpoint, "_csrf_exempt", False):
        return
    await csrf_protect.validate_csrf(request)
