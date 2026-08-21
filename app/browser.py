import re
from pathlib import Path


def solve_captcha_svg(svg: str) -> str:
    items = []
    rx = re.compile(r'<(?:text|tspan)\b[^>]*\bx="([\d.]+)"[^>]*>([^<]*)</(?:text|tspan)>', re.I)
    for m in rx.finditer(svg):
        items.append((float(m.group(1) or 0), m.group(2)))
    if not items:
        rs = re.compile(r'<(?:text|tspan)\b[^>]*>([^<]*)</(?:text|tspan)>', re.I)
        for i, m in enumerate(rs.finditer(svg)):
            items.append((i, m.group(1)))
    return "".join(ch for _, ch in sorted(items, key=lambda p: p[0])).strip()


def guess_ext(content_type: str, content_disposition: str) -> str:
    m = (re.search(r'filename\*?=(?:UTF-8\'\'|"?)([^";]+)', content_disposition, re.I)
         or re.search(r'filename="?([^";]+)"?', content_disposition, re.I))
    if m:
        ext = Path(m.group(1)).suffix
        if ext:
            return ext.lstrip(".")
    ct = (content_type or "").lower()
    if "zip" in ct:
        return "zip"
    if "spreadsheetml" in ct or "xlsx" in ct or "excel" in ct:
        return "xlsx"
    if "csv" in ct:
        return "csv"
    if "pdf" in ct:
        return "pdf"
    return "bin"
