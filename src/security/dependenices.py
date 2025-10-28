from fastapi import HTTPException, status, Depends, Header

from config.dependencies import get_jwt_auth_manager
from database import UserGroupModel, UserGroupEnum
from security.interfaces import JWTAuthManagerInterface
from security.utils import check_authentication


def require_authentication(
        authorization: str | None = Header(None),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> int:
    payload = check_authentication(authorization, jwt_manager)
    return payload["user_id"]


def require_moderator_or_admin(
        authorization: str | None = Header(None),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> int:
    payload = check_authentication(authorization, jwt_manager)

    if payload["role"] not in (UserGroupEnum.MODERATOR, UserGroupEnum.ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not moderator nor admin"
        )
    return payload["user_id"]


def require__admin(
        authorization: str | None = Header(None),
        jwt_manager: JWTAuthManagerInterface = Depends(get_jwt_auth_manager),
) -> int:
    payload = check_authentication(authorization, jwt_manager)

    if payload["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not admin"
        )
    return payload["user_id"]
