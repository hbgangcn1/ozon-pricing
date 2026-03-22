from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
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

router = APIRouter(prefix="/api/products", tags=["产品"])
security = HTTPBearer()


def get_current_user_id(api_key: str = Depends(security)) -> int:
    return 1


@router.get("", response_model=List[ProductResponse])
async def get_products(user_id: int = Depends(get_current_user_id)):
    products = get_all_products_for_user(user_id)
    return products


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(product_id: int, user_id: int = Depends(get_current_user_id)):
    product = get_product_by_id(product_id, user_id)
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return product


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
async def create_product(
    product: ProductCreate, user_id: int = Depends(get_current_user_id)
):
    product_data = product.model_dump()
    product_id = add_product(product_data)
    if not product_id:
        raise HTTPException(status_code=400, detail="创建产品失败")
    return get_product_by_id(product_id, user_id)


@router.put("/{product_id}", response_model=ProductResponse)
async def update_product_endpoint(
    product_id: int, product: ProductUpdate, user_id: int = Depends(get_current_user_id)
):
    existing = get_product_by_id(product_id, user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="产品不存在")

    update_data = product.model_dump(exclude_unset=True)
    success = update_product(product_id, user_id, update_data)
    if not success:
        raise HTTPException(status_code=400, detail="更新产品失败")

    return get_product_by_id(product_id, user_id)


@router.delete("/{product_id}", response_model=MessageResponse)
async def delete_product_endpoint(
    product_id: int, user_id: int = Depends(get_current_user_id)
):
    success = delete_product(product_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="产品不存在或删除失败")
    return MessageResponse(message="删除成功")
