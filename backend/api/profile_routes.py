from fastapi import APIRouter

from backend.api.schemas import UserProfile, UserProfileUpdateRequest
from backend.dependencies import CurrentUserDep, UserServiceDep

router = APIRouter(prefix="/api", tags=["profile"])


@router.get("/profile", response_model=UserProfile)
async def get_profile(
        current_user: CurrentUserDep,
        user_service: UserServiceDep,
):
    """Return the authenticated user's profile."""
    return await user_service.get_user_repo_by_id(current_user.id)


@router.patch("/profile", response_model=UserProfile)
async def update_profile(
        user_profile: UserProfileUpdateRequest,
        current_user: CurrentUserDep,
        user_service: UserServiceDep,
):
    """Update editable profile fields for the authenticated user.

    Only fields present in the request body are updated (partial update).
    login, role, created_at, and updated_at cannot be changed through this endpoint.
    """
    return await user_service.update_user_repo(current_user.id, user_profile)