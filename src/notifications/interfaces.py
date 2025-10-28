from abc import ABC, abstractmethod


class EmailSenderInterface(ABC):
    """
    Abstract base class defining the interface for sending different types of emails.

    This interface is designed for asynchronous email sending operations.
    Any concrete implementation should provide actual logic to send emails
    for user activation, notifications, and password resets.

    Methods:
        send_activation_email: Send an account activation email with a link.
        send_notification_email: Send a generic notification email with subject and text.
        send_activation_complete_email: Send a confirmation email after activation.
        send_password_reset_email: Send an email to reset the user's password.
        send_password_reset_complete_email: Send a confirmation email after password reset.
    """

    @abstractmethod
    async def send_activation_email(self, email: str, activation_link: str) -> None:
        """
        Send an account activation email to the specified email address.

        Args:
            email (str): The recipient's email address.
            activation_link (str): The activation URL the user should visit to activate their account.

        Returns:
            None
        """
        pass

    @abstractmethod
    async def send_notification_email(
        self,
        email: str,
        subject: str,
        notification_text: str,
        notification_title: str
    ) -> None:
        """
        Send a generic notification email.

        Args:
            email (str): The recipient's email address.
            subject (str): The email subject line.
            notification_text (str): The main content of the notification email.
            notification_title (str): The title or header displayed in the email.

        Returns:
            None
        """
        pass

    @abstractmethod
    async def send_activation_complete_email(self, email: str, login_link: str) -> None:
        """
        Send a confirmation email after account activation is complete.

        Args:
            email (str): The recipient's email address.
            login_link (str): The URL the user can use to log in.

        Returns:
            None
        """
        pass

    @abstractmethod
    async def send_password_reset_email(self, email: str, reset_link: str) -> None:
        """
        Send an email to the user to reset their password.

        Args:
            email (str): The recipient's email address.
            reset_link (str): The password reset URL.

        Returns:
            None
        """
        pass

    @abstractmethod
    async def send_password_reset_complete_email(self, email: str, login_link: str) -> None:
        """
        Send a confirmation email after the user has successfully reset their password.

        Args:
            email (str): The recipient's email address.
            login_link (str): The URL the user can use to log in.

        Returns:
            None
        """
        pass
