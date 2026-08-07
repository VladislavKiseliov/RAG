from typing import Any, Dict

from fastapi import APIRouter, Depends
from backend.dependencies import  AuthServiceDep
from backend.schemas.schemas import LoginRequest, RegisterRequest, RefreshRequest, LogoutRequest
from backend.utils.rate_limit import enforce_login_rate_limit, enforce_register_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    status_code=201,
    response_model=Dict[str, Any],
    dependencies=[Depends(enforce_register_rate_limit)],
)
async def register(
        user_data: RegisterRequest,
        auth_service: AuthServiceDep,
):
    """Register a new user account.

    Validates that the login is unique, hashes the password with bcrypt,
    and persists the new user to the database.

    Returns 409 if the login is already taken.
    Returns 422 if the password is shorter than 8 characters or passwords do not match.
    """
    return await auth_service.register(
        username=user_data.username,
        password=user_data.password
    )


@router.post("/login", response_model=Dict[str, Any], dependencies=[Depends(enforce_login_rate_limit)])
async def login(
        user_data: LoginRequest,
        auth_service: AuthServiceDep,
) -> Dict[str, Any]:
    """Authenticate a user and issue a JWT access token + refresh token pair.

    Both "user not found" and "wrong password" cases return 401 to prevent
    user enumeration attacks.

    Returns 401 if credentials are invalid.
    """
    return await auth_service.login(user_data.username, user_data.password)


@router.post("/refresh", response_model=Dict[str, Any])
async def refresh_token(
        request: RefreshRequest,
        auth_service: AuthServiceDep,
) -> Dict[str, Any]:
    """Rotate a refresh token and issue a new access + refresh token pair.

    The old refresh token is revoked atomically when the new one is issued.
    Clients must replace both tokens after a successful refresh.

    Returns 401 if the token is not found, already revoked, or expired.
    """
    return await auth_service.refresh(request.refresh_token)


@router.post("/logout", response_model=Dict[str, Any])
async def logout(
        request: LogoutRequest,
        auth_service: AuthServiceDep,
) -> Dict[str, Any]:
    """Revoke a refresh token to log the user out.

    If revoke_all is true, all active sessions for the user are terminated.
    Idempotent: returns success even if the token is already revoked.
    """
    return await auth_service.logout(
        refresh_token=request.refresh_token,
        revoke_all=request.revoke_all
    )