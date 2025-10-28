import pytest
from unittest.mock import patch, MagicMock
from celery_apps.email_tasks import send_email, BaseEmailError

@pytest.mark.asyncio
async def test_send_email_success():
    email = "from@example.com"
    recipient = "to@example.com"
    subject = "Test Subject"
    html_content = "<p>Hello</p>"
    api_key = "fake_api_key"

    mock_response = MagicMock()
    mock_response.status_code = 202

    with patch("celery_apps.email_tasks.SendGridAPIClient") as mock_client:
        mock_client.return_value.send.return_value = mock_response

        send_email(email, subject, html_content, api_key, recipient)
        mock_client.assert_called_once_with(api_key)
        mock_client.return_value.send.assert_called_once()

@pytest.mark.asyncio
async def test_send_email_failure_status_code():
    email = "from@example.com"
    recipient = "to@example.com"
    subject = "Test Subject"
    html_content = "<p>Hello</p>"
    api_key = "fake_api_key"

    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.headers = {"error": "bad request"}

    with patch("celery_apps.email_tasks.SendGridAPIClient") as mock_client:
        mock_client.return_value.send.return_value = mock_response

        with pytest.raises(BaseEmailError) as exc_info:
            send_email(email, subject, html_content, api_key, recipient)
        assert "Failed to send email" in str(exc_info.value)

@pytest.mark.asyncio
async def test_send_email_raises_exception():
    email = "from@example.com"
    recipient = "to@example.com"
    subject = "Test Subject"
    html_content = "<p>Hello</p>"
    api_key = "fake_api_key"

    with patch("celery_apps.email_tasks.SendGridAPIClient") as mock_client:
        mock_client.return_value.send.side_effect = Exception("Network error")

        with pytest.raises(BaseEmailError) as exc_info:
            send_email(email, subject, html_content, api_key, recipient)
        assert "Failed to send email" in str(exc_info.value)
