import logging
import os
import tempfile
from typing import List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError, StatementError
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import (
    get_current_user_id,
    require_admin,
)
from database import get_db
from db.logistics_crud import create_logistics
from db.priority_group import recalculate_priority_groups
from models.user import User
from services.plan_resolution import (
    count_user_active_rules,
    get_effective_logistics_limit,
)
from db.logistics_pool import (
    delete_all,
    get_all,
    get_by_id,
    get_by_ids,
    upsert,
    set_active,
)
from xlsx_import import parse_file

router = APIRouter(prefix="/api/logistics-pool", tags=["物流池"])
logger = logging.getLogger(__name__)
_MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB
_MAX_IMPORT_ROWS = 50000
_COPY_EXCLUDE = {"id", "source_file", "imported_at", "is_active"}
_VALID_VOLUME_MODES = {"none", "max_actual_vs_volume", "longest_side", "sum_of_sides"}


def _raise_upload_too_large() -> None:
    raise HTTPException(
        status_code=413,
        detail=f"文件大小超过限制（最大 {_MAX_UPLOAD_SIZE // 1024 // 1024}MB）",
    )


async def _read_upload_content(file: UploadFile) -> bytes:
    size = getattr(file, "size", None)
    if size is not None and size > _MAX_UPLOAD_SIZE:
        _raise_upload_too_large()
    content = await file.read(_MAX_UPLOAD_SIZE + 1)
    if len(content) > _MAX_UPLOAD_SIZE:
        _raise_upload_too_large()
    return content


def _sanitize_pool_data(data: dict) -> dict:
    vm = data.get("volume_mode")
    if vm and vm not in _VALID_VOLUME_MODES:
        data["volume_mode"] = "none"
    if data.get("min_days") is None:
        data["min_days"] = 0
    if data.get("max_days") is None:
        data["max_days"] = 0
    return data


async def _check_logistics_limit(
    session: AsyncSession,
    user_id: int,
    import_count: int,
) -> None:
    user = await session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="用户不存在")

    if getattr(user, "role", None) == "admin":
        return

    await session.execute(
        text("SELECT pg_advisory_xact_lock(:lock_key)"),
        {"lock_key": user_id},
    )
    limit = await get_effective_logistics_limit(session, user)
    if limit == -1:
        return

    current = await count_user_active_rules(session, user_id)
    if current + import_count > limit:
        raise HTTPException(
            status_code=403,
            detail=f"已达到您当前方案的物流规则上限（{limit} 条）",
        )


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


@router.post("/import", dependencies=[Depends(require_admin)])
async def import_logistics_pool(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 格式文件")
    temp_path = ""
    try:
        content = await _read_upload_content(file)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx") as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        try:
            result = parse_file(
                temp_path,
                source_file=file.filename or None,
                max_import_rows=_MAX_IMPORT_ROWS,
            )
        except ValueError as exc:
            logger.warning("物流池导入解析失败: %s", exc)
            detail = str(exc)
            if "导入行数不能超过" in detail:
                raise HTTPException(status_code=413, detail=detail) from exc
            raise HTTPException(
                status_code=400,
                detail="上传文件格式有误，请检查后重试",
            ) from exc
        except PermissionError as exc:
            logger.warning("物流池导入文件被占用: %s", exc)
            raise HTTPException(
                status_code=423,
                detail="文件被占用，请关闭OneDrive同步后重试",
            ) from exc
        imported = 0
        skipped = result.get("skipped", 0)
        errors = list(result.get("errors", []))
        rows = result.get("rows", [])
        if len(rows) > _MAX_IMPORT_ROWS:
            raise HTTPException(
                status_code=413,
                detail=f"导入行数不能超过 {_MAX_IMPORT_ROWS} 行",
            )
        for index, row in enumerate(rows, start=1):
            try:
                await upsert(session, row)
                imported += 1
            except Exception as exc:
                skipped += 1
                errors.append(f"第 {index} 行导入失败")
                logger.warning("物流池导入第 %d 行失败: %s", index, exc, exc_info=True)
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
            detail="导入处理失败，请联系管理员",
        )
    finally:
        await file.close()
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
            detail="删除失败，请联系管理员",
        )


@router.post("/{pool_id}/add-to-my-logistics")
async def add_to_my_logistics(
    pool_id: int,
    user_id: int = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_db),
):
    await _check_logistics_limit(session, user_id, 1)
    item = await get_by_id(session, pool_id)
    if not item:
        raise HTTPException(status_code=404, detail="物流池条目不存在")
    data = {k: v for k, v in item.items() if k not in _COPY_EXCLUDE}
    _sanitize_pool_data(data)
    async with session.begin_nested():
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
    await _check_logistics_limit(session, user_id, len(body.ids))
    added = []
    not_found = []
    errors: list[str] = []
    pool_items = await get_by_ids(session, body.ids)
    for pool_id in body.ids:
        item = pool_items.get(pool_id)
        if not item:
            not_found.append(pool_id)
            continue
        data = {k: v for k, v in item.items() if k not in _COPY_EXCLUDE}
        _sanitize_pool_data(data)
        try:
            async with session.begin_nested():
                new_id = await create_logistics(session, user_id, data)
        except IntegrityError as exc:
            name = data.get("name", pool_id)
            pgcode = getattr(exc.orig, "pgcode", None) if exc.orig else None
            if pgcode == "23505":
                errors.append(f"{name}: 已存在")
            elif pgcode:
                errors.append(f"{name}: 数据库错误({pgcode})")
            else:
                errors.append(f"{name}: {exc}")
            logger.warning("batch-add 跳过 pool_id=%s: %s", pool_id, exc)
        except DBAPIError as exc:
            # connection_invalidated 必须中止整批 (spec.md:38, design.md D2)
            if getattr(exc, "connection_invalidated", False):
                logger.exception("batch-add 连接失效，中止整批")
                raise
            # 其它 DBAPI 子类 (DataError / ProgrammingError / OperationalError 等) 单条跳过
            name = data.get("name", pool_id)
            errors.append(f"{name}: {exc}")
            logger.warning("batch-add 跳过 pool_id=%s DB 错误: %s", pool_id, exc)
        except StatementError as exc:
            # 非 DBAPI 的 StatementError (绑定/编译阶段错误等)，单条跳过
            name = data.get("name", pool_id)
            errors.append(f"{name}: {exc}")
            logger.warning("batch-add 跳过 pool_id=%s 语句错误: %s", pool_id, exc)
        else:
            added.append(new_id)
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
