from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    COMMISSION_ALLOWED_TIERS,
    get_current_user_id,
    get_user_with_subscription,
)
from api.models.schemas import MessageResponse
from database import get_db
from db.commission_categories import create, get_all, get_by_id, soft_delete, update

router = APIRouter(prefix="/api/commission-categories", tags=["佣金类目"])


def _ensure_commission_write_access(user: dict) -> int:
    if user.get("role") == "admin":
        return user["id"]
    subscription_type = user.get("subscription_type") or "free"
    if subscription_type not in COMMISSION_ALLOWED_TIERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="此功能需要专业版或更高订阅等级",
        )
    return user["id"]


class CategoryBody(BaseModel):
    name: str = Field(..., min_length=1)
    rfbs_tier1_rate: float
    rfbs_tier2_rate: float
    rfbs_tier3_rate: float


class CategoryPatch(BaseModel):
    name: Optional[str] = Field(None, min_length=1)
    rfbs_tier1_rate: Optional[float] = None
    rfbs_tier2_rate: Optional[float] = None
    rfbs_tier3_rate: Optional[float] = None
    is_active: Optional[int] = None


class CategoryOut(BaseModel):
    id: int
    user_id: int
    name: str
    rfbs_tier1_rate: float
    rfbs_tier2_rate: float
    rfbs_tier3_rate: float
    fbp_tier1_rate: float
    fbp_tier2_rate: float
    fbp_tier3_rate: float
    is_active: int


@router.get("", response_model=list[CategoryOut])
async def list_categories(
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    return await get_all(session, include_inactive=False, user_id=user_id)


@router.post("", response_model=CategoryOut, status_code=status.HTTP_201_CREATED)
async def create_category(
    body: CategoryBody,
    user: dict = Depends(get_user_with_subscription),
    session: AsyncSession = Depends(get_db),
):
    user_id = _ensure_commission_write_access(user)
    data = body.model_dump()
    data["user_id"] = user_id
    data["fbp_tier1_rate"] = round(body.rfbs_tier1_rate - 0.01, 4)
    data["fbp_tier2_rate"] = round(body.rfbs_tier2_rate - 0.01, 4)
    data["fbp_tier3_rate"] = round(body.rfbs_tier3_rate - 0.01, 4)
    data["is_active"] = 1
    category_id = await create(session, data)
    if category_id is None:
        raise HTTPException(status_code=400, detail="佣金类目名称已存在")
    item = await get_by_id(session, category_id, user_id)
    if not item:
        raise HTTPException(status_code=500, detail="创建后查询失败")
    return item


@router.patch("/{category_id}", response_model=CategoryOut)
async def update_category(
    category_id: int,
    body: CategoryPatch,
    user: dict = Depends(get_user_with_subscription),
    session: AsyncSession = Depends(get_db),
):
    user_id = _ensure_commission_write_access(user)
    if not await get_by_id(session, category_id, user_id):
        raise HTTPException(status_code=404, detail="佣金类目不存在")
    data = body.model_dump(exclude_unset=True)
    if "rfbs_tier1_rate" in data:
        data["fbp_tier1_rate"] = round(data["rfbs_tier1_rate"] - 0.01, 4)
    if "rfbs_tier2_rate" in data:
        data["fbp_tier2_rate"] = round(data["rfbs_tier2_rate"] - 0.01, 4)
    if "rfbs_tier3_rate" in data:
        data["fbp_tier3_rate"] = round(data["rfbs_tier3_rate"] - 0.01, 4)
    if not data:
        item = await get_by_id(session, category_id, user_id)
        if not item:
            raise HTTPException(status_code=404, detail="佣金类目不存在")
        return item
    if not await update(session, category_id, data, user_id):
        raise HTTPException(status_code=400, detail="更新失败，可能名称重复")
    item = await get_by_id(session, category_id, user_id)
    if not item:
        raise HTTPException(status_code=404, detail="更新后查询失败")
    return item


@router.delete("/{category_id}", response_model=MessageResponse)
async def delete_category(
    category_id: int,
    user: dict = Depends(get_user_with_subscription),
    session: AsyncSession = Depends(get_db),
):
    user_id = _ensure_commission_write_access(user)
    if not await soft_delete(session, category_id, user_id):
        raise HTTPException(status_code=404, detail="佣金类目不存在")
    return MessageResponse(message="删除成功")
