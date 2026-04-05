from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.products import (
    add_product,
    get_all_products_for_user,
    get_product_by_id,
    update_product,
    delete_product,
)
from api.models.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    MessageResponse,
)
from api.dependencies import get_current_user_id

router = APIRouter(prefix="/api/products", tags=["产品"])


@router.get("", response_model=List[ProductResponse])
async def get_products(
    user_id: int = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    products = await get_all_products_for_user(session, user_id)
    return products[offset : offset + limit]


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    product = await get_product_by_id(session, product_id, user_id)
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return product


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    product_data = product.model_dump()
    for key in ["is_cylinder", "has_battery", "has_liquid", "has_msds"]:
        if key in product_data and isinstance(product_data[key], bool):
            product_data[key] = 1 if product_data[key] else 0
    product_id = await add_product(session, user_id, product_data)
    if not product_id:
        raise HTTPException(status_code=400, detail="创建产品失败")
    result = await get_product_by_id(session, product_id, user_id)
    if not result:
        raise HTTPException(status_code=400, detail="创建产品失败")
    return result


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product_endpoint(
    product_id: int,
    product: ProductUpdate,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    existing = await get_product_by_id(session, product_id, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="产品不存在")

    update_data = product.model_dump(exclude_unset=True)
    for key in ["is_cylinder", "has_battery", "has_liquid", "has_msds"]:
        if key in update_data and isinstance(update_data[key], bool):
            update_data[key] = 1 if update_data[key] else 0
    success = await update_product(session, product_id, user_id, update_data)
    if not success:
        raise HTTPException(status_code=400, detail="更新产品失败")

    result = await get_product_by_id(session, product_id, user_id)
    if not result:
        raise HTTPException(status_code=404, detail="产品不存在")
    return result


@router.delete("/{product_id}", response_model=MessageResponse)
async def delete_product_endpoint(
    product_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    success = await delete_product(session, product_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="产品不存在或删除失败")
    return MessageResponse(message="删除成功")
