# -*- coding: utf-8 -*-
"""SEC-W13-02: Excel 导入异常路径 tmp 文件必须清理。"""
import os
import asyncio
from unittest.mock import patch, AsyncMock, MagicMock

import pytest
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_preview_import_cleans_tmp_on_parse_failure():
    """解析失败时 finally 必须删除 tmp 文件。"""
    from api.routes import products as products_route

    captured = {}

    def fake_parse(temp_path, suffix):
        captured["path"] = temp_path
        # 验证文件确实在解析过程中存在
        assert os.path.exists(temp_path), "tmp 文件解析时应存在"
        raise ValueError("simulated parse failure")

    fake_user = {"id": 1, "username": "u", "subscription_type": "free"}
    fake_session = MagicMock()
    fake_file = MagicMock()
    fake_file.filename = "evil.xlsx"
    fake_file.read = AsyncMock(return_value=b"fake xlsx bytes")
    fake_file.close = AsyncMock(return_value=None)

    with patch.object(products_route, "_ensure_excel_access", return_value=1), \
         patch.object(products_route, "_read_upload_contents", new=AsyncMock(return_value=b"x")), \
         patch.object(products_route, "_parse_product_import_file", side_effect=fake_parse):
        with pytest.raises(HTTPException) as exc:
            await products_route.preview_product_import(
                file=fake_file, user=fake_user, session=fake_session
            )
        assert exc.value.status_code == 400

    # tmp 文件必须已被 finally 清理
    assert "path" in captured, "解析未被调用"
    assert not os.path.exists(captured["path"]), (
        f"异常后 tmp 文件未清理: {captured['path']}"
    )


@pytest.mark.asyncio
async def test_preview_import_rejects_invalid_suffix():
    """非 xlsx/xls 后缀立即拒绝，不创建 tmp 文件。"""
    from api.routes import products as products_route

    fake_user = {"id": 1, "username": "u", "subscription_type": "free"}
    fake_session = MagicMock()
    fake_file = MagicMock()
    fake_file.filename = "evil.exe"
    fake_file.close = AsyncMock(return_value=None)

    with patch.object(products_route, "_ensure_excel_access", return_value=1):
        with pytest.raises(HTTPException) as exc:
            await products_route.preview_product_import(
                file=fake_file, user=fake_user, session=fake_session
            )
        assert exc.value.status_code == 400
