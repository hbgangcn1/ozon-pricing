import os
import re

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

from db_utils import get_db_connection, _safe_adapt_sql
from api.models.schemas import MessageResponse
from api.dependencies import require_admin

router = APIRouter(prefix="/api/settings", tags=["设置"])

_SAFE_BACKUP_NAME = re.compile(r"^[a-zA-Z0-9_.\-]+\.dump$")


def _sanitize_backup_filename(filename: str) -> str:
    """Sanitize backup filename to prevent path traversal."""
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
    """延迟导入，避免循环依赖"""
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


# ---------------------------------------------------------------------------
# 系统设置
# ---------------------------------------------------------------------------


@router.get("", response_model=SystemConfigResponse)
async def get_settings(admin: int = Depends(require_admin)):
    with get_db_connection() as (conn, c):
        sql_raw = "SELECT config_key, config_value FROM system_config"
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(sql)
        config = {}
        for row in c.fetchall():
            config[row[0]] = row[1]

    _, _, _, _, get_auto_backup_settings, _, _, _, _, _, _ = _load_backup_service()
    settings = get_auto_backup_settings()

    return SystemConfigResponse(
        open_registration=config.get("open_registration", "true").lower() == "true",
        backup_interval=settings.get("interval_hours", 6),
    )


@router.put("/open-registration", response_model=MessageResponse)
async def update_open_registration(enabled: bool, admin: int = Depends(require_admin)):
    with get_db_connection() as (conn, c):
        sql_raw = """
            INSERT INTO system_config (config_key, config_value, updated_at)
            VALUES ('open_registration', %s, %s)
            ON CONFLICT (config_key) DO UPDATE SET config_value = %s, updated_at = %s
        """
        sql = _safe_adapt_sql(sql_raw, conn)
        c.execute(
            sql,
            (
                str(enabled).lower(),
                datetime.now(),
                str(enabled).lower(),
                datetime.now(),
            ),
        )
        conn.commit()
    return MessageResponse(message="设置已更新")


# ---------------------------------------------------------------------------
# 备份文件列表
# ---------------------------------------------------------------------------


@router.get("/backups", response_model=List[BackupInfo])
async def get_backups(admin: int = Depends(require_admin)):
    """获取所有备份文件"""
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


# ---------------------------------------------------------------------------
# 手动备份
# ---------------------------------------------------------------------------


@router.post("/backup", response_model=MessageResponse)
async def create_backup(admin: int = Depends(require_admin)):
    """立即执行一次手动备份"""
    _, _, _, create_manual_backup, _, _, _, _, _, _, _ = _load_backup_service()

    try:
        success = create_manual_backup()
        if success:
            return MessageResponse(message="备份成功")
        else:
            return JSONResponse(
                status_code=500,
                content={"message": "备份失败，请检查服务器日志"},
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"备份异常: {str(e)}"},
        )


# ---------------------------------------------------------------------------
# 备份设置
# ---------------------------------------------------------------------------


@router.get("/backup/settings", response_model=BackupSettingsResponse)
async def get_backup_settings(admin: int = Depends(require_admin)):
    """获取自动备份设置"""
    _, _, _, _, get_auto_backup_settings, _, _, _, _, _, _ = _load_backup_service()
    settings = get_auto_backup_settings()

    # 计算下次备份时间
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
    """更新自动备份设置"""
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
        return JSONResponse(
            status_code=500,
            content={"message": f"更新失败: {str(e)}"},
        )


# ---------------------------------------------------------------------------
# 备份统计
# ---------------------------------------------------------------------------


@router.get("/backup/stats", response_model=BackupStatsResponse)
async def get_backup_stats(admin: int = Depends(require_admin)):
    """获取备份统计信息"""
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
        count=stats.get("count", 0),
        total_size_mb=stats.get("total_size_mb", 0.0),
        files=files,
    )


# ---------------------------------------------------------------------------
# 下载备份文件
# ---------------------------------------------------------------------------


@router.get("/backup/{filename}/download")
async def download_backup(filename: str, admin: int = Depends(require_admin)):
    """下载备份文件"""
    _, _, _, _, _, _, _, _, _, read_backup_file, _ = _load_backup_service()

    filename = _sanitize_backup_filename(filename)

    # 安全检查：只允许下载 .dump 文件
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


# ---------------------------------------------------------------------------
# 删除备份文件
# ---------------------------------------------------------------------------


@router.delete("/backup/{filename}", response_model=MessageResponse)
async def delete_backup(filename: str, admin: int = Depends(require_admin)):
    """删除指定的备份文件"""
    _, _, _, _, _, _, _, _, delete_backup_file, _, _ = _load_backup_service()

    filename = _sanitize_backup_filename(filename)

    if not filename.endswith(".dump"):
        return JSONResponse(
            status_code=400,
            content={"message": "只允许删除 .dump 文件"},
        )

    try:
        success = delete_backup_file(filename)
        if success:
            return MessageResponse(message=f"已删除: {filename}")
        else:
            return JSONResponse(
                status_code=404,
                content={"message": "备份文件不存在或删除失败"},
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"删除失败: {str(e)}"},
        )


# ---------------------------------------------------------------------------
# 从备份恢复
# ---------------------------------------------------------------------------


@router.post("/backup/{filename}/restore", response_model=MessageResponse)
async def restore_backup(
    filename: str,
    req: RestoreRequest,
    admin: int = Depends(require_admin),
):
    """从指定备份文件恢复数据库"""
    _, _, _, _, _, _, _, _, _, _, restore_database = _load_backup_service()

    filename = _sanitize_backup_filename(filename)

    if not filename.endswith(".dump"):
        return JSONResponse(
            status_code=400,
            content={"message": "只允许从 .dump 文件恢复"},
        )

    try:
        success = restore_database(
            filename,
            create_snapshot=req.create_snapshot,
        )
        if success:
            return MessageResponse(message=f"已从 {filename} 恢复数据库")
        else:
            return JSONResponse(
                status_code=500,
                content={"message": "恢复失败，请检查服务器日志"},
            )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"message": f"恢复异常: {str(e)}"},
        )
