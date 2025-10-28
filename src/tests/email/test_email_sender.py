import pytest
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_send_notification_email(email_sender):
    mock_template = MagicMock()
    mock_template.render.return_value = "<html>Notification</html>"
    email_sender._env.get_template.return_value = mock_template

    await email_sender.send_notification_email(
        email="user@example.com",
        subject="Test Subject",
        notification_text="Something happened",
        notification_title="Test Title"
    )

    email_sender._env.get_template.assert_called_once_with("notification.html")
    mock_template.render.assert_called_once_with(
        email="user@example.com",
        notification_text="Something happened",
        notification_title="Test Title"
    )
    email_sender._send_email.assert_awaited_once_with(
        "user@example.com",
        "Test Subject",
        "<html>Notification</html>"
    )


@pytest.mark.asyncio
async def test_send_activation_email(email_sender):
    mock_template = MagicMock()
    mock_template.render.return_value = "<html>Activation</html>"
    email_sender._env.get_template.return_value = mock_template

    await email_sender.send_activation_email("user@example.com", "http://link.com")

    email_sender._env.get_template.assert_called_once_with("activate.html")
    mock_template.render.assert_called_once_with(
        email="user@example.com",
        activation_link="http://link.com"
    )
    email_sender._send_email.assert_awaited_once_with(
        "user@example.com",
        "Account Activation",
        "<html>Activation</html>"
    )


@pytest.mark.asyncio
async def test_send_activation_complete_email(email_sender):
    mock_template = MagicMock()
    mock_template.render.return_value = "<html>Activated</html>"
    email_sender._env.get_template.return_value = mock_template

    await email_sender.send_activation_complete_email("user@example.com", "http://login.com")

    email_sender._env.get_template.assert_called_once_with("activate_done.html")
    mock_template.render.assert_called_once_with(email="user@example.com", login_link="http://login.com")
    email_sender._send_email.assert_awaited_once_with(
        "user@example.com",
        "Account Activated Successfully",
        "<html>Activated</html>"
    )


@pytest.mark.asyncio
async def test_send_password_reset_email(email_sender):
    mock_template = MagicMock()
    mock_template.render.return_value = "<html>Reset</html>"
    email_sender._env.get_template.return_value = mock_template

    await email_sender.send_password_reset_email("user@example.com", "http://reset.com")

    email_sender._env.get_template.assert_called_once_with("reset.html")
    mock_template.render.assert_called_once_with(email="user@example.com", reset_link="http://reset.com")
    email_sender._send_email.assert_awaited_once_with(
        "user@example.com",
        "Password Reset Request",
        "<html>Reset</html>"
    )


@pytest.mark.asyncio
async def test_send_password_reset_complete_email(email_sender):
    mock_template = MagicMock()
    mock_template.render.return_value = "<html>Reset Done</html>"
    email_sender._env.get_template.return_value = mock_template

    await email_sender.send_password_reset_complete_email("user@example.com", "http://login.com")

    email_sender._env.get_template.assert_called_once_with("reset_done.html")
    mock_template.render.assert_called_once_with(email="user@example.com", login_link="http://login.com")
    email_sender._send_email.assert_awaited_once_with(
        "user@example.com",
        "Your Password Has Been Successfully Reset",
        "<html>Reset Done</html>"
    )
