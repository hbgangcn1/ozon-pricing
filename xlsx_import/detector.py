from pathlib import Path

import openpyxl
from openpyxl.workbook.workbook import Workbook


KEYWORDS = (
    ("Russia-China CP", "china_post"),
    ("CHINA rFBS", "scoring_rfbs"),
    ("KZ & BY", "cis_rfbs"),
    ("Other CIS", "cis_rfbs"),
    ("CHINA FBP", "fbp"),
)

FILENAME_PATTERNS = (
    ("china_post", "china_post"),
    ("china_scoring", "scoring_rfbs"),
    ("cis_delivery_methods", "cis_rfbs"),
    ("fbp_list_of_services", "fbp"),
)


def detect_format(source: str | Workbook) -> str:
    if isinstance(source, str):
        filename = Path(source).name.lower()
        for needle, fmt in FILENAME_PATTERNS:
            if needle in filename:
                return fmt
        wb = openpyxl.load_workbook(source, read_only=True)
        try:
            return detect_format(wb)
        finally:
            wb.close()

    wb = source
    titles = [ws.title for ws in wb.worksheets]
    for keyword, fmt in KEYWORDS:
        needle = keyword.lower()
        if any(needle in title.lower() for title in titles):
            return fmt
    supported = [kw for kw, _ in KEYWORDS]
    raise ValueError(f"无法识别xlsx格式。工作表: {titles}；支持的关键词: {supported}")
