import logging
import os
import shutil
import tempfile
import time

import openpyxl

from xlsx_import.detector import detect_format
from xlsx_import.parsers import china_post, cis_rfbs, fbp, scoring_rfbs

logger = logging.getLogger(__name__)

PARSERS = {
    "china_post": china_post.parse,
    "scoring_rfbs": scoring_rfbs.parse,
    "cis_rfbs": cis_rfbs.parse,
    "fbp": fbp.parse,
}

_MAX_RETRIES = 3
_INITIAL_BACKOFF = 0.1
MAX_IMPORT_ROWS = 50000


def _load_workbook_read_only(path: str):
    try:
        return openpyxl.load_workbook(path, read_only=True, data_only=True)
    except TypeError as exc:
        if "read_only" not in str(exc):
            raise
        return openpyxl.load_workbook(path, data_only=True)


def _open_workbook_with_retry(filepath: str):
    temp_path = ""
    delay = _INITIAL_BACKOFF
    last_error: PermissionError | None = None
    try:
        for attempt in range(_MAX_RETRIES + 1):
            candidate = temp_path or filepath
            try:
                workbook = _load_workbook_read_only(candidate)
                return workbook, temp_path
            except PermissionError as exc:
                last_error = exc
                if attempt >= _MAX_RETRIES:
                    break
                if not temp_path:
                    with tempfile.NamedTemporaryFile(
                        delete=False, suffix=".xlsx"
                    ) as handle:
                        temp_path = handle.name
                    shutil.copy2(filepath, temp_path)
                time.sleep(delay)
                delay *= 2
        raise last_error or PermissionError(filepath)
    except Exception:
        logger.debug("清理临时Excel文件失败", exc_info=True)
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
        raise


def parse_file(
    filepath: str,
    source_file: str | None = None,
    max_import_rows: int | None = None,
) -> dict:
    workbook, temp_path = _open_workbook_with_retry(filepath)
    try:
        fmt = detect_format(workbook)
        limit = max_import_rows or MAX_IMPORT_ROWS
        if max_import_rows is None:
            result = PARSERS[fmt](workbook, filepath, source_file)
        else:
            result = PARSERS[fmt](
                workbook,
                filepath,
                source_file,
                max_import_rows=limit,
            )
        if len(result.get("rows", [])) > limit:
            raise ValueError(f"导入行数不能超过 {limit} 行")
        result["format"] = fmt
        return result
    finally:
        workbook.close()
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
