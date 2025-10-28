from datetime import datetime, timezone
from typing import cast

from fastapi import APIRouter, Depends, status, HTTPException, BackgroundTasks, Request
from fastapi_csrf_protect import CsrfProtect
from sqlalchemy import select, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette.responses import JSONResponse

from config import get_jwt_auth_manager, get_settings, BaseAppSettings, get_accounts_email_notificator
from database import (
    get_db,
    UserModel,
    UserGroupModel,
    UserGroupEnum,
    ActivationTokenModel,
    PasswordResetTokenModel,
    RefreshTokenModel, CartModel
)
from decorators.custom_decorators import csrf_exempt
from exceptions import BaseSecurityError
from notifications import EmailSenderInterface
from schemas import (
    UserRegistrationRequestSchema,
    UserRegistrationResponseSchema,
    MessageResponseSchema,
    UserActivationRequestSchema,
    PasswordResetRequestSchema,
    PasswordResetCompleteRequestSchema,
    UserLoginResponseSchema,
    UserLoginRequestSchema,
    TokenRefreshRequestSchema,
    TokenRefreshResponseSchema
)
from security.interfaces import JWTAuthManagerInterface

router = APIRouter()


@csrf_exempt
@router.post(
    "/register/",
    response_model=UserRegistrationResponseSchema,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
        user_data: UserRegistrationRequestSchema,
        request: Request,
        db: AsyncSession = Depends(get_db),
        settings: BaseAppSettings = Depends(get_settings),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> UserRegistrationResponseSchema:
    """
    Endpoint for user registration.

    Registers a new user, hashes their password, and assigns them to the default user group.
    If a user with the same email already exists, an HTTP 409 error is raised.
    In case of any unexpected issues during the creation process, an HTTP 500 error is returned.
    Args:
        :param db:
        :param user_data:
        :param request:
        :param email_sender:
        :param settings:

    Returns:
        UserRegistrationResponseSchema: The newly created user's details.

    Raises:
        HTTPException:
            - 409 Conflict if a user with the same email exists.
            - 500 Internal Server Error if an error occurs during user creation.
    """
    result = await db.execute(
        select(UserModel)
        .where(UserModel.email == user_data.email)
    )
    existing_user = result.scalars().first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A user with this email {user_data.email} already exists."
        )

    result = await db.execute(
        select(UserGroupModel)
        .where(UserGroupModel.name == UserGroupEnum.USER)
    )
    user_group = result.scalars().first()
    if not user_group:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Default user group not found."
        )

    try:
        new_user = UserModel.create(
            email=str(user_data.email),
            raw_password=user_data.password,
            group_id=user_group.id,
        )
        db.add(new_user)
        await db.flush()

        activation_token = ActivationTokenModel(user_id=new_user.id)
        db.add(activation_token)

        await db.commit()
        await db.refresh(new_user)
        activation_url = (
            f"{settings.FRONTEND_URL}/"
            f"{str(request.url_for('activate_account')).replace(str(request.base_url), '')}"
            f"?token={activation_token.token}"
        )
        await email_sender.send_activation_email(new_user.email, activation_url)
    except SQLAlchemyError as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred during user creation."
        ) from e
    else:
        return UserRegistrationResponseSchema.model_validate(new_user)


@csrf_exempt
@router.post(
    "/activate/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def activate_account(
        activation_data: UserActivationRequestSchema,
        request: Request,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        settings: BaseAppSettings = Depends(get_settings),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    """
    Activate a user's account using an activation token.

    This endpoint validates the provided activation token for a user. If the token exists and has not expired,
    and the user's account is not already active, the user's account will be activated. The activation token
    is then removed from the database. If the token is invalid, expired, or the account is already active,
    a 400 Bad Request error is returned.

    Args:
        activation_data (UserActivationRequestSchema): Contains the user's email and activation token.
        request (Request): The incoming HTTP request.
        background_tasks (BackgroundTasks): FastAPI background tasks for sending emails or other async tasks.
        db (AsyncSession, optional): Async database session. Defaults to dependency-injected session.
        settings (BaseAppSettings, optional): Application settings. Defaults to dependency-injected settings.
        email_sender (EmailSenderInterface, optional): Email sending service for notifications.
         Defaults to dependency-injected sender.

    Returns:
        MessageResponseSchema: A message confirming successful activation.

    Raises:
        HTTPException 400:
            - If the activation token is invalid or expired.
            - If the user account is already active.
    """
    stmt = (
        select(ActivationTokenModel)
        .options(joinedload(ActivationTokenModel.user))
        .join(UserModel)
        .where(
            UserModel.email == activation_data.email,
            ActivationTokenModel.token == activation_data.token
        )
    )
    result = await db.execute(stmt)
    token_record = result.scalars().first()

    now_utc = datetime.now(timezone.utc)
    if not token_record or token_record.expires_at.replace(tzinfo=timezone.utc) < now_utc:  # type: ignore
        if token_record:
            await db.delete(token_record)
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired activation token."
        )

    user = token_record.user
    if user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User account is already active."
        )

    user.is_active = True

    await db.delete(token_record)
    cart = CartModel(user_id=user.id)
    db.add(cart)
    await db.commit()

    login_url = (
        f"{settings.FRONTEND_URL}/"
        f"{str(request.url_for('login_user')).replace(str(request.base_url), '')}"
    )
    background_tasks.add_task(
        email_sender.send_activation_complete_email,
        user.email,
        str(login_url)
    )

    return MessageResponseSchema(message="User account activated successfully.")


@router.post(
    "/password-reset/request/",
    response_model=MessageResponseSchema,
    status_code=status.HTTP_200_OK,
)
async def request_password_reset_token(
        data: PasswordResetRequestSchema,
        request: Request,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        settings: BaseAppSettings = Depends(get_settings),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    """
    Request a password reset token for a user account.

    This endpoint generates a password reset token for the given email if the user exists and is active.
    Any previous tokens for this user are invalidated. The endpoint always returns a success message to
    prevent revealing whether an email is registered in the system.

    Args:
        data (PasswordResetRequestSchema): Contains the user's email address.
        request (Request): The incoming HTTP request.
        background_tasks (BackgroundTasks): FastAPI background tasks for sending the password reset email.
        db (AsyncSession, optional): Async database session. Defaults to dependency-injected session.
        settings (BaseAppSettings, optional): Application settings, e.g., email templates or expiration times.
        email_sender (EmailSenderInterface, optional): Email sending service to dispatch reset instructions.

    Returns:
        MessageResponseSchema: A message indicating that password reset instructions will be sent if the user exists.

    Notes:
        - Does not indicate whether a user exists to avoid information leakage.
        - The actual reset email is sent asynchronously via background tasks.
    """
    result = await db.execute(
        select(UserModel)
        .filter_by(email=data.email)
    )
    user = result.scalars().first()

    if not user or not user.is_active:
        return MessageResponseSchema(
            message="If you are registered, you will receive an email with instructions."
        )

    await db.execute(delete(PasswordResetTokenModel).where(PasswordResetTokenModel.user_id == user.id))

    reset_token = PasswordResetTokenModel(user_id=cast(int, user.id))
    db.add(reset_token)

    await db.commit()
    reset_pass_url = (
        f"{settings.FRONTEND_URL}/"
        f"{str(request.url_for('reset_password')).replace(str(request.base_url), '')}"
        f"?token={reset_token.token}"
    )
    background_tasks.add_task(
        email_sender.send_password_reset_email,
        user.email,
        str(reset_pass_url)
    )
    return MessageResponseSchema(
        message="If you are registered, you will receive an email with instructions."
    )


@router.post(
    "/reset-password/complete/",
    response_model=MessageResponseSchema,
)
async def reset_password(
        data: PasswordResetCompleteRequestSchema,
        request: Request,
        background_tasks: BackgroundTasks,
        db: AsyncSession = Depends(get_db),
        settings: BaseAppSettings = Depends(get_settings),
        email_sender: EmailSenderInterface = Depends(get_accounts_email_notificator),
) -> MessageResponseSchema:
    """
     Reset a user's password using a password reset token.

     This endpoint verifies the provided token for the given email. If the token is valid and not expired,
     the user's password is updated to the new password provided, and the token is deleted to prevent reuse.
     If the token is invalid, expired, or the email does not exist, an error is returned.

     Args:
         data (PasswordResetCompleteRequestSchema): Contains the user's email, reset token, and new password.
         request (Request): The incoming HTTP request.
         background_tasks (BackgroundTasks): FastAPI background tasks for sending notifications if needed.
         db (AsyncSession, optional): Async database session. Defaults to dependency-injected session.
         settings (BaseAppSettings, optional): Application settings, e.g., password rules or token expiration times.
         email_sender (EmailSenderInterface, optional): Email sending service to notify user of successful reset.

     Returns:
         MessageResponseSchema: A message confirming that the password was successfully reset.

     Raises:
         HTTPException 400:
             - If the reset token is invalid, expired, or does not match the email.
         HTTPException 500:
             - If an unexpected error occurs while updating the password or deleting the token.

     Notes:
         - Tokens are single-use and deleted after a successful reset.
         - Background tasks can be used for post-reset notifications.
     """
    result = await db.execute(
        select(UserModel)
        .filter_by(email=data.email)
    )
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or token."
        )

    result = await db.execute(
        select(PasswordResetTokenModel)
        .filter_by(user_id=user.id)
    )
    token_record = result.scalars().first()

    if not token_record or token_record.token != data.token:
        if token_record:
            await db.run_sync(lambda s: s.delete(token_record))
            await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or token."
        )

    expires_at = token_record.expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        await db.run_sync(lambda s: s.delete(token_record))
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid email or token."
        )

    try:
        user.password = data.password
        await db.run_sync(lambda s: s.delete(token_record))
        await db.commit()

        login_url = (
            f"{settings.FRONTEND_URL}/"
            f"{str(request.url_for('login_user')).replace(str(request.base_url), '')}"
        )
        background_tasks.add_task(
            email_sender.send_password_reset_complete_email,
            user.email,
            str(login_url)
        )

    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while resetting the password."
        )

    return MessageResponseSchema(message="Password reset successfully.")


@csrf_exempt
@router.post(
    "/login/",
    response_model=UserLoginResponseSchema,
)
async def login_user(
        login_data: UserLoginRequestSchema,
        db: AsyncSession = Depends(get_db),
        settings: BaseAppSettings = Depends(get_settings),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> UserLoginResponseSchema:
    """
    Endpoint for user login.

    Authenticates a user using their email and password.
    If authentication is successful, creates a new refresh token and returns both access and refresh tokens.

    Args:
        login_data (UserLoginRequestSchema): The login credentials.
        db (AsyncSession): The asynchronous database session.
        settings (BaseAppSettings): The application settings.
        jwt_manager (JWTAuthManagerInterface): The JWT authentication manager.

    Returns:
        UserLoginResponseSchema: A response containing the access and refresh tokens.

    Raises:
        HTTPException:
            - 401 Unauthorized if the email or password is invalid.
            - 403 Forbidden if the user account is not activated.
            - 500 Internal Server Error if an error occurs during token creation.
    """
    result = await db.execute(
        select(UserModel)
        .filter_by(email=login_data.email)
    )
    user = result.scalars().first()

    if not user or not user.verify_password(login_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not activated.",
        )

    jwt_refresh_token = jwt_manager.create_refresh_token({"user_id": user.id})

    try:
        refresh_token = RefreshTokenModel.create(
            user_id=user.id,
            days_valid=settings.LOGIN_TIME_DAYS,
            token=jwt_refresh_token
        )
        db.add(refresh_token)
        await db.flush()
        await db.commit()
    except SQLAlchemyError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while processing the request.",
        )

    jwt_access_token = jwt_manager.create_access_token({"user_id": user.id, "role": UserGroupEnum.USER})
    return UserLoginResponseSchema(
        access_token=jwt_access_token,
        refresh_token=jwt_refresh_token,
    )


@router.post(
    "/refresh/",
    response_model=TokenRefreshResponseSchema,
)
async def refresh_access_token(
        token_data: TokenRefreshRequestSchema,
        db: AsyncSession = Depends(get_db),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> TokenRefreshResponseSchema:
    """
    Endpoint to refresh an access token.

    Validates the provided refresh token, extracts the user ID from it, and issues
    a new access token. If the token is invalid or expired, an error is returned.

    Args:
        token_data (TokenRefreshRequestSchema): Contains the refresh token.
        db (AsyncSession): The asynchronous database session.
        jwt_manager (JWTAuthManagerInterface): JWT authentication manager.

    Returns:
        TokenRefreshResponseSchema: A new access token.

    Raises:
        HTTPException:
            - 400 Bad Request if the token is invalid or expired.
            - 401 Unauthorized if the refresh token is not found.
            - 404 Not Found if the user associated with the token does not exist.
    """
    try:
        decoded_token = jwt_manager.decode_refresh_token(token_data.refresh_token)
        user_id = decoded_token.get("user_id")
    except BaseSecurityError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    result = await db.execute(
        select(RefreshTokenModel)
        .filter_by(token=token_data.refresh_token)
    )
    refresh_token_record = result.scalars().first()
    if not refresh_token_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token not found.",
        )

    result = await db.execute(select(UserModel).filter_by(id=user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    new_access_token = jwt_manager.create_access_token({"user_id": user_id, "role": UserGroupEnum.USER})

    return TokenRefreshResponseSchema(access_token=new_access_token)


@csrf_exempt
@router.get("/csrf")
def get_csrf(csrf_protect: CsrfProtect = Depends()):
    token, signed_token = csrf_protect.generate_csrf_tokens()
    response = JSONResponse({"csrf_token": token})
    csrf_protect.set_csrf_cookie(signed_token, response)
    return response
