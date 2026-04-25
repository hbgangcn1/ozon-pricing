import openpyxl
from openpyxl.workbook.workbook import Workbook

KEYWORDS = (
    ("china to russia by cp", "china_post"),
    ("china to cis by cp", "china_post"),
    ("china post", "china_post"),
    ("china rfbs", "scoring_rfbs"),
    ("rfbs", "scoring_rfbs"),
    ("scoring", "scoring_rfbs"),
    ("kz & by", "cis_rfbs"),
    ("other cis", "cis_rfbs"),
    ("cis delivery", "cis_rfbs"),
    ("cis", "cis_rfbs"),
    ("china fbp", "fbp"),
    ("fbp", "fbp"),
)

DEPRECATED_CHINA_POST_SHEETS = {"russia-china cp"}


def _detect_by_sheet_names(titles: list[str]) -> str | None:
    lowered = [t.lower() for t in titles]
    for needle, fmt in KEYWORDS:
        if any(needle in title for title in lowered):
            return fmt
    return None


def _cell_text(ws, row: int, col: int) -> str:
    val = ws.cell(row, col).value
    if val is None:
        return ""
    return str(val).replace("\u00a0", " ").strip().lower()


def _detect_by_headers(wb: Workbook) -> str | None:
    for ws in wb.worksheets:
        if "\u4e2d\u6587" in (ws.title or ""):
            continue

        # china_post (NEW two-sheet layout): row5 col2="delivery method",
        # col3="price", col18="tarification"
        r5c2 = _cell_text(ws, 5, 2)
        r5c3 = _cell_text(ws, 5, 3)
        if (
            "delivery method" in r5c2
            and "price" in r5c3
            and "tarification" in _cell_text(ws, 5, 18)
        ):
            return "china_post"

        # cis_rfbs: row5 col1="scoring group", col4="delivery method"
        r5c1 = _cell_text(ws, 5, 1)
        r5c4 = _cell_text(ws, 5, 4)
        if "scoring" in r5c1 and "delivery" in r5c4:
            return "cis_rfbs"

        # scoring_rfbs: 18-col layout, row5 col1 has content, col19 empty
        if "scoring" in r5c1 or "priority" in r5c1:
            r5c19 = _cell_text(ws, 5, 19)
            if not r5c19:
                return "scoring_rfbs"

        # fbp: data starts row8, "fbp" in row7/8 or "service" header row7
        r7c1 = _cell_text(ws, 7, 1)
        r8c1 = _cell_text(ws, 8, 1)
        if "fbp" in r7c1 or "fbp" in r8c1:
            return "fbp"
        r7c3 = _cell_text(ws, 7, 3)
        if ("service" in r7c3 or "\u670d\u52a1" in r7c3) and r8c1:
            return "fbp"

    return None


def detect_format(source: str | Workbook) -> str:
    if isinstance(source, str):
        wb = openpyxl.load_workbook(source, read_only=True)
        try:
            return detect_format(wb)
        finally:
            wb.close()

    wb = source
    titles = [ws.title for ws in wb.worksheets]

    lowered_titles = [t.lower().strip() for t in titles]
    for deprecated in DEPRECATED_CHINA_POST_SHEETS:
        if any(deprecated == t or deprecated in t for t in lowered_titles):
            raise ValueError(
                "\u65e0\u6cd5\u8bc6\u522bxlsx\u683c\u5f0f: "
                "\u68c0\u6d4b\u5230\u65e7\u7248 China Post (Russia-China CP) "
                "\u5de5\u4f5c\u8868\uff0c\u5df2\u4e0d\u518d\u652f\u6301\u3002"
                "\u8bf7\u8054\u7cfb\u4f9b\u5e94\u5546\u83b7\u53d6\u65b0\u7248 ePacket "
                f"\u6587\u4ef6\u3002\u5de5\u4f5c\u8868: {titles}"
            )

    result = _detect_by_sheet_names(titles)
    if result:
        return result

    result = _detect_by_headers(wb)
    if result:
        return result

    supported = [kw for kw, _ in KEYWORDS]
    raise ValueError(
        f"\u65e0\u6cd5\u8bc6\u522bxlsx\u683c\u5f0f\u3002\u5de5\u4f5c\u8868: {titles}\uff1b\u652f\u6301\u7684\u5173\u952e\u8bcd: {supported}"
    )
