import logging
import os
import tempfile
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_id, require_admin
from database import get_db
from db.logistics_crud import create_logistics
from db.priority_group import recalculate_priority_groups
from db.logistics_pool import delete_all, get_all, get_by_id, insert_row, set_active
from xlsx_import import parse_file

router = APIRouter(prefix="/api/logistics-pool", tags=["物流池"])
logger = logging.getLogger(__name__)
_COPY_EXCLUDE = {"id", "source_file", "imported_at", "is_active"}
_VALID_VOLUME_MODES = {"none", "max_actual_vs_volume", "longest_side", "sum_of_sides"}


def _sanitize_pool_data(data: dict) -> dict:
    vm = data.get("volume_mode")
    if vm and vm not in _VALID_VOLUME_MODES:
        data["volume_mode"] = "none"
    if data.get("min_days") is None:
        data["min_days"] = 0
    if data.get("max_days") is None:
        data["max_days"] = 0
    return data


class ActiveBody(BaseModel):
    is_active: int


class BatchAddBody(BaseModel):
    ids: List[int]


@router.get("")
async def list_logistics_pool(
    user_id: int = Depends(get_current_user_id),
    fulfillment_type: Optional[str] = None,
    destination: Optional[str] = None,
    fbp_service_level: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    items, total = await get_all(
        session,
        fulfillment_type=fulfillment_type,
        destination=destination,
        fbp_service_level=fbp_service_level,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.post("/import")
async def import_logistics_pool(
    file: UploadFile = File(...),
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
            temp_file.write(await file.read())
            temp_path = temp_file.name
        try:
            result = parse_file(temp_path, source_file=file.filename or None)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except PermissionError as exc:
            logger.warning("物流池导入文件被占用: %s", exc)
            raise HTTPException(
                status_code=423,
                detail="文件被占用，请关闭OneDrive同步后重试",
            ) from exc
        imported = 0
        skipped = result.get("skipped", 0)
        errors = list(result.get("errors", []))
        for index, row in enumerate(result.get("rows", []), start=1):
            try:
                await insert_row(session, row)
                imported += 1
            except Exception as exc:
                skipped += 1
                errors.append(f"row {index}: {exc}")
        return {"imported": imported, "skipped": skipped, "errors": errors}
    except HTTPException:
        raise
    except PermissionError as exc:
        logger.warning("物流池导入文件被占用: %s", exc)
        raise HTTPException(
            status_code=423,
            detail="文件被占用，请关闭OneDrive同步后重试",
        ) from exc
    except Exception as exc:
        logger.exception("物流池导入失败: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"导入处理失败: {exc}",
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)


@router.delete("/all")
async def delete_all_logistics_pool(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    try:
        count = await delete_all(session)
        return {"deleted": count}
    except Exception as exc:
        logger.exception("物流池删除全部失败: %s", exc)
        raise HTTPException(
            status_code=500,
            detail=f"删除失败: {exc}",
        )


@router.post("/{pool_id}/add-to-my-logistics")
async def add_to_my_logistics(
    pool_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    item = await get_by_id(session, pool_id)
    if not item:
        raise HTTPException(status_code=404, detail="物流池条目不存在")
    data = {k: v for k, v in item.items() if k not in _COPY_EXCLUDE}
    _sanitize_pool_data(data)
    new_id = await create_logistics(session, user_id, data)
    await recalculate_priority_groups(session, user_id)
    return {"id": new_id}


@router.post("/batch-add-to-my-logistics")
async def batch_add_to_my_logistics(
    body: BatchAddBody,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    if not body.ids:
        raise HTTPException(status_code=400, detail="ids 不能为空")
    if len(body.ids) > 200:
        raise HTTPException(status_code=400, detail="单次最多添加 200 条")
    added = []
    not_found = []
    errors: list[str] = []
    for pool_id in body.ids:
        item = await get_by_id(session, pool_id)
        if not item:
            not_found.append(pool_id)
            continue
        data = {k: v for k, v in item.items() if k not in _COPY_EXCLUDE}
        _sanitize_pool_data(data)
        try:
            new_id = await create_logistics(session, user_id, data)
            added.append(new_id)
        except IntegrityError as exc:
            await session.rollback()
            name = data.get("name", pool_id)
            errors.append(f"{name}: {exc.orig}")
            logger.warning("batch-add 跳过 pool_id=%s: %s", pool_id, exc.orig)
    if added:
        await recalculate_priority_groups(session, user_id)
    return {
        "added": len(added),
        "not_found": not_found,
        "new_ids": added,
        "errors": errors,
    }


@router.patch("/{pool_id}")
async def set_logistics_pool_active(
    pool_id: int,
    body: ActiveBody,
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    if body.is_active not in {0, 1}:
        raise HTTPException(status_code=400, detail="is_active 只能是 0 或 1")
    if not await set_active(session, pool_id, body.is_active):
        raise HTTPException(status_code=404, detail="物流池条目不存在")
    item = await get_by_id(session, pool_id)
    if not item:
        raise HTTPException(status_code=404, detail="更新后查询失败")
    return item
