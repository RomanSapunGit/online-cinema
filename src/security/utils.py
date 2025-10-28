import secrets

from fastapi import HTTPException
from starlette import status

from exceptions import TokenExpiredError
from security.interfaces import JWTAuthManagerInterface


def generate_secure_token(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def check_authentication(authorization: str, jwt_manager: JWTAuthManagerInterface) -> dict:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header is missing")

    auth_header_list = authorization.split()
    if len(auth_header_list) != 2 or auth_header_list[0].lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'"
        )

    token = auth_header_list[1]
    try:
        payload = jwt_manager.decode_access_token(token)
    except TokenExpiredError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has expired.")
    return payload
