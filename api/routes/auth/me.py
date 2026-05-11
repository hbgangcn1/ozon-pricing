from fastapi import Depends

from api.dependencies import get_current_user as get_current_user_dep
from api.models.schemas import UserResponse

from ._router import router


@router.get("/me", response_model=UserResponse)
async def get_me(
    user: dict = Depends(get_current_user_dep),
):
    return UserResponse(
        id=user["id"],
        username=user["username"],
        role=user["role"],
        user_type=user.get("user_type") or "free",
        subscription_type=user.get("subscription_type") or "free",
        has_security_question=bool(user.get("security_q1")),
        remaining_calculations=(
            user["remaining_calculations"]
            if user.get("remaining_calculations") is not None
            else -1
        ),
        trial_used=user.get("trial_used") or 0,
        trial_started_at=user.get("trial_started_at") or 0,
        trial_expires_at=user.get("trial_expires_at") or 0,
        trial_plan_at_start=user.get("trial_plan_at_start") or "",
    )
