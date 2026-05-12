import asyncio
import logging
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
    get_products_by_names,
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
from api.dependencies import (
    EXCEL_ALLOWED_TIERS,
    get_current_user_id,
    get_user_with_subscription,
)

router = APIRouter(prefix="/api/products", tags=["产品"])
logger = logging.getLogger(__name__)
MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_IMPORT_ROWS = 50000


async def _get_existing_products_for_import(
    session: AsyncSession,
    user_id: int,
    rows: list[dict],
    column_mapping: dict[str, str],
) -> dict[str, dict]:
    name_column = column_mapping.get("name")
    if not name_column:
        return {}
    names = []
    for row in rows:
        name = row.get(name_column)
        if isinstance(name, str):
            stripped = name.strip()
            if stripped:
                names.append(stripped)
        elif name:
            names.append(str(name))
    unique_names = list(dict.fromkeys(names))
    return await get_products_by_names(session, user_id, unique_names)


def _ensure_excel_access(user: dict) -> int:
    if user.get("role") == "admin":
        return user["id"]
    subscription_type = user.get("subscription_type") or "free"
    if subscription_type not in EXCEL_ALLOWED_TIERS:
        raise HTTPException(
            status_code=403,
            detail="此功能需要企业版或更高订阅等级",
        )
    return user["id"]


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


def _raise_upload_too_large() -> None:
    raise HTTPException(status_code=413, detail="文件大小不能超过 20MB")


async def _read_upload_contents(file: UploadFile) -> bytes:
    size = getattr(file, "size", None)
    if size is not None and size > MAX_UPLOAD_SIZE:
        _raise_upload_too_large()
    contents = await file.read(MAX_UPLOAD_SIZE + 1)
    if len(contents) > MAX_UPLOAD_SIZE:
        _raise_upload_too_large()
    return contents


@router.get("", response_model=List[ProductResponse])
async def get_products(
    user_id: int = Depends(get_current_user_id),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    products = await get_all_products_for_user(
        session, user_id, limit=limit, offset=offset,
    )
    return products


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


def _parse_xlsx_preview(temp_path: str) -> ProductImportPreview:
    workbook = openpyxl.load_workbook(
        temp_path,
        read_only=True,
        data_only=True,
    )
    try:
        sheet = workbook.active
        if sheet is None:
            return ProductImportPreview(columns=[], preview_rows=[])
        row_iterator = sheet.iter_rows(values_only=True)
        try:
            header_row = next(row_iterator)
        except StopIteration:
            return ProductImportPreview(columns=[], preview_rows=[])
        headers = [
            str(value).strip() if value is not None else ""
            for value in header_row
        ]
        headers = [h for h in headers if h]
        preview_rows = []
        for row_count, row in enumerate(row_iterator, start=1):
            if row_count > MAX_IMPORT_ROWS:
                raise HTTPException(
                    status_code=413,
                    detail=f"导入行数不能超过 {MAX_IMPORT_ROWS} 行",
                )
            row_dict = {}
            for index, column in enumerate(headers):
                if column:
                    row_dict[column] = (
                        _safe_value(row[index])
                        if index < len(row)
                        else None
                    )
            preview_rows.append(row_dict)
        return ProductImportPreview(
            columns=headers,
            preview_rows=preview_rows,
        )
    finally:
        workbook.close()


def _parse_xls_preview(temp_path: str) -> ProductImportPreview:
    import xlrd
    workbook = xlrd.open_workbook(temp_path)
    sheet = workbook.sheet_by_index(0)
    if sheet.nrows == 0:
        return ProductImportPreview(columns=[], preview_rows=[])
    if sheet.nrows - 1 > MAX_IMPORT_ROWS:
        raise HTTPException(
            status_code=413,
            detail=f"导入行数不能超过 {MAX_IMPORT_ROWS} 行",
        )
    header_row = sheet.row_values(0)
    if not header_row:
        return ProductImportPreview(columns=[], preview_rows=[])
    headers = [
        str(value).strip() if value is not None else ""
        for value in header_row
    ]
    headers = [h for h in headers if h]
    preview_rows = []
    for row_idx in range(1, sheet.nrows):
        row = sheet.row_values(row_idx)
        row_dict = {}
        for index, column in enumerate(headers):
            if column:
                row_dict[column] = (
                    _safe_value(row[index]) if index < len(row) else None
                )
        preview_rows.append(row_dict)
    return ProductImportPreview(columns=headers, preview_rows=preview_rows)


def _parse_product_import_file(
    temp_path: str, suffix: str
) -> ProductImportPreview:
    if suffix == ".xlsx":
        return _parse_xlsx_preview(temp_path)
    return _parse_xls_preview(temp_path)


@router.post("/import/preview", response_model=ProductImportPreview)
async def preview_product_import(
    file: UploadFile,
    user: dict = Depends(get_user_with_subscription),
    session: AsyncSession = Depends(get_db),
):
    _ensure_excel_access(user)
    suffix = os.path.splitext(file.filename or "")[1].lower()
    if suffix not in (".xlsx", ".xls"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 或 .xls 文件")

    contents = await _read_upload_contents(file)

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(contents)
            temp_path = temp_file.name

        return await asyncio.to_thread(
            _parse_product_import_file, temp_path, suffix
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("xlsx 解析失败: %s", exc)
        raise HTTPException(
            status_code=400, detail="解析 xlsx 失败，请检查文件格式"
        ) from exc
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@router.post("/import/confirm")
async def confirm_product_import(
    payload: ProductImportConfirm,
    user: dict = Depends(get_user_with_subscription),
    session: AsyncSession = Depends(get_db),
):
    user_id = _ensure_excel_access(user)
    if payload.conflict_action not in {"skip", "overwrite"}:
        raise HTTPException(status_code=400, detail="conflict_action 无效")

    imported = 0
    skipped = 0
    errors = []
    existing_products = await _get_existing_products_for_import(
        session,
        user_id,
        payload.rows,
        payload.column_mapping,
    )

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
        if isinstance(name, str):
            name = name.strip()
            transformed["name"] = name

        try:
            existing = existing_products.get(name)
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
                existing_products[name] = {**existing, **product_data}
                imported += 1
                continue

            product_id = await add_product(session, user_id, product_data)
            if not product_id:
                errors.append(f"第 {index} 行导入失败: {name}")
                continue
            existing_products[name] = {"id": product_id, **product_data, "user_id": user_id}
            imported += 1
        except Exception as exc:
            logger.warning("产品导入第 %d 行处理失败: %s", index, exc, exc_info=True)
            errors.append(f"第 {index} 行处理失败")

    return {"imported": imported, "skipped": skipped, "errors": errors}
