import os
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, cast
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession

from database import get_db, engine
from db.config import get_all_config, set_system_config
from api.models.schemas import MessageResponse
from api.dependencies import require_admin

router = APIRouter(prefix="/api/settings", tags=["设置"])

_SAFE_BACKUP_NAME = re.compile(r"^[a-zA-Z0-9_.\-]+\.dump$")


def _sanitize_backup_filename(filename: str) -> str:
    safe_name = os.path.basename(filename)
    if not _SAFE_BACKUP_NAME.match(safe_name):
        raise HTTPException(status_code=400, detail="非法的备份文件名")
    return safe_name


class SystemConfigResponse(BaseModel):
    open_registration: bool
    backup_interval: int = 6


class BackupInfo(BaseModel):
    name: str
    size: str
    size_bytes: int
    time: str
    type: str = "auto"


class BackupSettingsResponse(BaseModel):
    enabled: bool
    interval_hours: int
    max_backups: int
    next_backup: Optional[str] = None


class BackupStatsResponse(BaseModel):
    count: int
    total_size_mb: float
    files: List[BackupInfo]


class RestoreRequest(BaseModel):
    create_snapshot: bool = True


def _load_backup_service():
    from postgres_backup_service import (
        backup_system,
        start_backup_service,
        stop_backup_service,
        create_manual_backup,
        get_auto_backup_settings,
        update_auto_backup_settings,
        list_backup_files,
        get_backup_info,
        delete_backup_file,
        read_backup_file,
        restore_database,
    )

    return (
        backup_system,
        start_backup_service,
        stop_backup_service,
        create_manual_backup,
        get_auto_backup_settings,
        update_auto_backup_settings,
        list_backup_files,
        get_backup_info,
        delete_backup_file,
        read_backup_file,
        restore_database,
    )


@router.get("", response_model=SystemConfigResponse)
async def get_settings(
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    config_list = await get_all_config(session)
    config = {item["config_key"]: item["config_value"] for item in config_list}

    _, _, _, _, get_auto_backup_settings, _, _, _, _, _, _ = _load_backup_service()
    settings = get_auto_backup_settings()

    return SystemConfigResponse(
        open_registration=config.get("open_registration", "true").lower() == "true",
        backup_interval=settings.get("interval_hours", 6),
    )


@router.put("/open-registration", response_model=MessageResponse)
async def update_open_registration(
    enabled: bool,
    admin: int = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    await set_system_config(session, "open_registration", str(enabled).lower())
    return MessageResponse(message="设置已更新")


@router.get("/backups", response_model=List[BackupInfo])
async def get_backups(admin: int = Depends(require_admin)):
    _, _, _, _, _, _, list_backup_files, _, _, _, _ = _load_backup_service()
    records = list_backup_files()

    backups = []
    for r in records:
        size = r.get("size", 0)
        size_str = (
            f"{size / 1024:.1f} KB"
            if size < 1024 * 1024
            else f"{size / 1024 / 1024:.2f} MB"
        )
        mtime = r.get("mtime")
        if hasattr(mtime, "strftime"):
            time_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = str(mtime)

        backups.append(
            BackupInfo(
                name=r.get("name", ""),
                size=size_str,
                size_bytes=size,
                time=time_str,
                type=r.get("type", "auto"),
            )
        )

    backups.sort(key=lambda x: x.time, reverse=True)
    return backups


@router.post("/backup", response_model=MessageResponse)
async def create_backup(admin: int = Depends(require_admin)):
    _, _, _, create_manual_backup, _, _, _, _, _, _, _ = _load_backup_service()

    try:
        success = create_manual_backup()
        if success:
            return MessageResponse(message="备份成功")
        else:
            raise HTTPException(
                status_code=500,
                detail="备份失败，请检查服务器日志",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"备份异常: {str(e)}",
        )


@router.get("/backup/settings", response_model=BackupSettingsResponse)
async def get_backup_settings(admin: int = Depends(require_admin)):
    _, _, _, _, get_auto_backup_settings, _, _, _, _, _, _ = _load_backup_service()
    settings = get_auto_backup_settings()

    next_backup = None
    if settings.get("enabled"):
        try:
            from datetime import timedelta

            next_backup = (
                datetime.now() + timedelta(hours=settings.get("interval_hours", 6))
            ).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            pass

    return BackupSettingsResponse(
        enabled=settings.get("enabled", True),
        interval_hours=settings.get("interval_hours", 6),
        max_backups=settings.get("max_backups", 28),
        next_backup=next_backup,
    )


class UpdateBackupSettingsRequest(BaseModel):
    enabled: Optional[bool] = None
    interval_hours: Optional[int] = None
    max_backups: Optional[int] = None


@router.put("/backup/settings", response_model=MessageResponse)
async def update_backup_settings(
    req: UpdateBackupSettingsRequest,
    admin: int = Depends(require_admin),
):
    _, _, _, _, _, update_auto_backup_settings, _, _, _, _, _ = _load_backup_service()

    kwargs = {}
    if req.enabled is not None:
        kwargs["enabled"] = req.enabled
    if req.interval_hours is not None:
        kwargs["interval_hours"] = req.interval_hours
    if req.max_backups is not None:
        kwargs["max_backups"] = req.max_backups

    if not kwargs:
        return MessageResponse(message="没有需要更新的设置")

    try:
        update_auto_backup_settings(**kwargs)
        return MessageResponse(message="备份设置已更新")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"更新失败: {str(e)}",
        )


@router.get("/backup/stats", response_model=BackupStatsResponse)
async def get_backup_stats(admin: int = Depends(require_admin)):
    _, _, _, _, _, _, _, get_backup_info, _, _, _ = _load_backup_service()
    stats = get_backup_info()

    files = []
    for r in stats.get("files", []):
        size = r.get("size", 0)
        size_str = (
            f"{size / 1024:.1f} KB"
            if size < 1024 * 1024
            else f"{size / 1024 / 1024:.2f} MB"
        )
        mtime = r.get("mtime")
        if hasattr(mtime, "strftime"):
            time_str = mtime.strftime("%Y-%m-%d %H:%M:%S")
        else:
            time_str = str(mtime)

        files.append(
            BackupInfo(
                name=r.get("name", ""),
                size=size_str,
                size_bytes=size,
                time=time_str,
                type=r.get("type", "auto"),
            )
        )

    return BackupStatsResponse(
        count=int(cast(int | float | str | None, stats.get("count", 0)) or 0),
        total_size_mb=float(
            cast(int | float | str | None, stats.get("total_size_mb", 0.0)) or 0.0
        ),
        files=files,
    )


@router.get("/backup/{filename}/download")
async def download_backup(filename: str, admin: int = Depends(require_admin)):
    _, _, _, _, _, _, _, _, _, read_backup_file, _ = _load_backup_service()

    filename = _sanitize_backup_filename(filename)

    if not filename.endswith(".dump"):
        raise HTTPException(status_code=400, detail="只允许下载 .dump 文件")

    try:
        data = read_backup_file(filename)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="备份文件不存在")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")

    return StreamingResponse(
        iter([data]),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(data)),
        },
    )


@router.delete("/backup/{filename}", response_model=MessageResponse)
async def delete_backup(filename: str, admin: int = Depends(require_admin)):
    _, _, _, _, _, _, _, _, delete_backup_file, _, _ = _load_backup_service()

    filename = _sanitize_backup_filename(filename)

    if not filename.endswith(".dump"):
        raise HTTPException(status_code=400, detail="只允许删除 .dump 文件")

    try:
        success = delete_backup_file(filename)
        if success:
            return MessageResponse(message=f"已删除: {filename}")
        else:
            raise HTTPException(
                status_code=404,
                detail="备份文件不存在或删除失败",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"删除失败: {str(e)}",
        )


@router.post("/backup/{filename}/restore", response_model=MessageResponse)
async def restore_backup(
    filename: str,
    req: RestoreRequest,
    admin: int = Depends(require_admin),
):
    _, _, _, _, _, _, _, _, _, _, restore_database = _load_backup_service()

    filename = _sanitize_backup_filename(filename)

    if not filename.endswith(".dump"):
        raise HTTPException(status_code=400, detail="只允许从 .dump 文件恢复")

    try:
        success = restore_database(
            filename,
            create_snapshot=req.create_snapshot,
        )
        if success:
            await engine.dispose()
            return MessageResponse(message=f"已从 {filename} 恢复数据库")
        else:
            raise HTTPException(
                status_code=500,
                detail="恢复失败，请检查服务器日志",
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"恢复异常: {str(e)}",
        )
