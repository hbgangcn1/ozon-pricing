from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import List

from db_utils import (
    get_all_products_for_user,
    get_product_by_id,
    add_product,
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
def get_products(
    user_id: int = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    products = get_all_products_for_user(user_id)
    return products[offset : offset + limit]


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: int, user_id: int = Depends(get_current_user_id)):
    product = get_product_by_id(product_id, user_id)
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return product


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(product: ProductCreate, user_id: int = Depends(get_current_user_id)):
    product_data = product.model_dump()
    product_data["user_id"] = user_id
    for key in ["is_cylinder", "has_battery", "has_liquid", "has_msds"]:
        if key in product_data and isinstance(product_data[key], bool):
            product_data[key] = 1 if product_data[key] else 0
    product_id = add_product(product_data)
    if not product_id:
        raise HTTPException(status_code=400, detail="创建产品失败")
    return get_product_by_id(product_id, user_id)


@router.put("/{product_id}", response_model=ProductResponse)
def update_product_endpoint(
    product_id: int, product: ProductUpdate, user_id: int = Depends(get_current_user_id)
):
    existing = get_product_by_id(product_id, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="产品不存在")

    update_data = product.model_dump(exclude_unset=True)
    for key in ["is_cylinder", "has_battery", "has_liquid", "has_msds"]:
        if key in update_data and isinstance(update_data[key], bool):
            update_data[key] = 1 if update_data[key] else 0
    success = update_product(product_id, user_id, update_data)
    if not success:
        raise HTTPException(status_code=400, detail="更新产品失败")

    return get_product_by_id(product_id, user_id)


@router.delete("/{product_id}", response_model=MessageResponse)
def delete_product_endpoint(
    product_id: int, user_id: int = Depends(get_current_user_id)
):
    success = delete_product(product_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="产品不存在或删除失败")
    return MessageResponse(message="删除成功")
