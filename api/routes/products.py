import math
import os
import tempfile
from datetime import date, datetime, time

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, status
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db
from db.products import (
    add_product,
    get_all_products_for_user,
    get_product_by_id,
    get_product_by_name,
    update_product,
    delete_product,
)
from api.models.schemas import (
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    MessageResponse,
    ProductImportPreview,
    ProductImportConfirm,
)
from api.dependencies import get_current_user_id

router = APIRouter(prefix="/api/products", tags=["产品"])


def _safe_value(v):
    if v is None:
        return None
    if isinstance(v, (str, bool)):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, (datetime, date, time)):
        return str(v)
    return str(v)


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


@router.post("/import/preview", response_model=ProductImportPreview)
async def preview_product_import(
    file: UploadFile,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix != ".xlsx":
        raise HTTPException(status_code=400, detail="仅支持 xlsx 文件")

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
            temp_file.write(await file.read())
            temp_path = temp_file.name

        workbook = openpyxl.load_workbook(temp_path, data_only=True)
        sheet = workbook.active
        if sheet is None:
            raise HTTPException(status_code=400, detail="xlsx 缺少可用工作表")
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return ProductImportPreview(columns=[], preview_rows=[])

        headers = [str(value).strip() if value is not None else "" for value in rows[0]]
        headers = [h for h in headers if h]
        preview_rows = []
        for row in rows[1:]:
            row_dict = {}
            for index, column in enumerate(headers):
                if column:
                    row_dict[column] = (
                        _safe_value(row[index]) if index < len(row) else None
                    )
            preview_rows.append(row_dict)
        return ProductImportPreview(columns=headers, preview_rows=preview_rows)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"解析 xlsx 失败: {exc}") from exc
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@router.post("/import/confirm")
async def confirm_product_import(
    payload: ProductImportConfirm,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if payload.conflict_action not in {"skip", "overwrite"}:
        raise HTTPException(status_code=400, detail="conflict_action 无效")

    imported = 0
    skipped = 0
    errors = []

    for index, row in enumerate(payload.rows, start=1):
        transformed = {
            field: row[column]
            for field, column in payload.column_mapping.items()
            if column in row
        }
        transformed["user_id"] = user_id

        name = transformed.get("name")
        if not name:
            errors.append(f"第 {index} 行缺少 name")
            continue

        try:
            existing = await get_product_by_name(session, user_id, name)
            product_data = {k: v for k, v in transformed.items() if k != "user_id"}

            for key in ["is_cylinder", "has_battery", "has_liquid", "has_msds"]:
                if key in product_data and isinstance(product_data[key], bool):
                    product_data[key] = 1 if product_data[key] else 0

            if existing:
                if payload.conflict_action == "skip":
                    skipped += 1
                    continue
                success = await update_product(
                    session,
                    existing["id"],
                    user_id,
                    product_data,
                )
                if not success:
                    errors.append(f"第 {index} 行覆盖失败: {name}")
                    continue
                imported += 1
                continue

            product_id = await add_product(session, user_id, product_data)
            if not product_id:
                errors.append(f"第 {index} 行导入失败: {name}")
                continue
            imported += 1
        except Exception as exc:
            errors.append(f"第 {index} 行处理失败: {exc}")

    return {"imported": imported, "skipped": skipped, "errors": errors}
