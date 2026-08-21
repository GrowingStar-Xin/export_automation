import csv
import glob
import os
import re
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET

import mysql.connector

from .config import settings

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NS = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

INT_RE = re.compile(r"^-?\d+$")
FLOAT_RE = re.compile(r"^-?(\d+\.\d*|\.\d+|\d+[eE][+-]?\d+|\d+\.\d+[eE][+-]?\d+)$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DT_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$")


def col_to_num(s: str) -> int:
    n = 0
    for ch in s.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def col_letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def read_xlsx_sheets(path: str) -> list[tuple[str, dict]]:
    z = zipfile.ZipFile(path)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(f"{NS}si"):
            shared.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    sheets = []
    if "xl/workbook.xml" in z.namelist():
        wb = ET.fromstring(z.read("xl/workbook.xml"))
        for s in wb.findall(f"{NS}sheets"):
            for sh in s.findall(f"{NS}sheet"):
                sheets.append((sh.get("name"), sh.get(f"{REL_NS}id")))
    rels = {}
    if "xl/_rels/workbook.xml.rels" in z.namelist():
        rr = ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        for rel in rr.findall(f"{REL_NS}Relationship"):
            rels[rel.get("Id")] = rel.get("Target")
    result = []
    for name, rid in sheets:
        target = rels.get(rid, "worksheets/sheet1.xml")
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        if target not in z.namelist():
            cand = "xl/worksheets/" + target.split("/")[-1]
            target = cand if cand in z.namelist() else target
        if target not in z.namelist():
            continue
        root = ET.fromstring(z.read(target))
        grid = {}
        for row in root.iter(f"{NS}row"):
            r = int(row.get("r"))
            for c in row.findall(f"{NS}c"):
                ref = c.get("r") or ""
                col = "".join(ch for ch in ref if ch.isalpha())
                t = c.get("t")
                val = ""
                if t == "inlineStr":
                    val = "".join(x.text or "" for x in c.iter(f"{NS}t"))
                else:
                    v = c.find(f"{NS}v")
                    if v is not None and v.text is not None:
                        val = v.text
                        if t == "s" and val != "":
                            try:
                                val = shared[int(val)]
                            except Exception:
                                pass
                grid[(r, col)] = val
        result.append((name, grid))
    return result


def read_csv_sheets(path: str) -> list[tuple[str, dict]]:
    with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
        rows = list(csv.reader(f))
    grid = {}
    for ri, row in enumerate(rows, start=1):
        for ci, val in enumerate(row, start=1):
            grid[(ri, col_letter(ci))] = val
    return [("data", grid)]


def detect_header(grid: dict) -> tuple[int | None, list[str]]:
    rows = sorted(set(r for (r, _c) in grid))

    def cnt(r):
        return sum(1 for (rr, _c), v in grid.items() if rr == r and str(v).strip() != "")

    best_r, best_score = None, -1
    for r in rows[:10]:
        c = cnt(r)
        following = sum(1 for rr in (r + 1, r + 2, r + 3) if cnt(rr) >= 1)
        score = c * 10 + following
        if score > best_score:
            best_r, best_score = r, score
    if best_r is None or cnt(best_r) < 2:
        return None, []
    cols = sorted(col_to_num(c) for (rr, c) in grid if rr == best_r and str(grid[(rr, c)]).strip() != "")
    maxc = max(cols)
    headers = [str(grid.get((best_r, col_letter(cn)), "")).strip() or f"col_{cn}" for cn in range(1, maxc + 1)]
    return best_r, headers


def sanitize(name: str, used: set) -> str:
    n = re.sub(r"[^\w一-鿿]+", "_", str(name).strip(), flags=re.UNICODE)
    n = re.sub(r"_+", "_", n).strip("_") or "col"
    if n[0].isdigit():
        n = "c_" + n
    n = n[:60]
    base, i = n, 2
    while n.lower() in used:
        n = f"{base}_{i}"
        i += 1
    used.add(n.lower())
    return n


def infer_type(vals: list[str]) -> str:
    if not vals:
        return "VARCHAR(255)"
    if all(INT_RE.match(v) for v in vals):
        return "BIGINT"
    if all(INT_RE.match(v) or FLOAT_RE.match(v) for v in vals):
        return "DOUBLE"
    if all(DATE_RE.match(v) for v in vals):
        return "DATE"
    if all(DT_RE.match(v) for v in vals):
        return "DATETIME"
    maxlen = max(len(v) for v in vals)
    return "TEXT" if maxlen > 255 else "VARCHAR(255)"


def table_name(file_stem: str, sheet: str, total_sheets: int, prefix: str = "") -> str:
    def clean(s):
        s = re.sub(r"[^\w一-鿿]+", "_", s, flags=re.UNICODE)
        s = re.sub(r"_+", "_", s).strip("_")
        return s or "t"

    parts = [clean(file_stem)]
    if not (total_sheets == 1 and re.match(r"^sheet\d+$", sheet, re.I)):
        parts.append(clean(sheet))
    name = "_".join(parts)
    if name[0].isdigit():
        name = "t_" + name
    name = name[:60]
    return (prefix + "_" + name) if prefix else name


def collect_files(args: list[str]) -> list[str]:
    files = []
    for a in args:
        if os.path.isdir(a):
            files += sorted(glob.glob(os.path.join(a, "*.xlsx")) + glob.glob(os.path.join(a, "*.xls")) + glob.glob(os.path.join(a, "*.csv")))
        elif a.lower().endswith(".zip"):
            dest = tempfile.mkdtemp(prefix="xlsx_import_")
            with zipfile.ZipFile(a) as z:
                z.extractall(dest)
            files += sorted(glob.glob(os.path.join(dest, "**", "*.xlsx"), recursive=True)
                            + glob.glob(os.path.join(dest, "**", "*.xls"), recursive=True)
                            + glob.glob(os.path.join(dest, "**", "*.csv"), recursive=True))
        elif a.lower().endswith((".xlsx", ".xls", ".csv")):
            files.append(a)
    seen, out = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _extract_rows(grid: dict, header_row: int, ncols: int) -> list[list[str]]:
    rows = []
    maxr = max(r for (r, _c) in grid)
    for r in range(header_row + 1, maxr + 1):
        vals = [str(grid.get((r, col_letter(cn)), "")).strip() for cn in range(1, ncols + 1)]
        if any(v != "" for v in vals):
            rows.append(vals)
    return rows


def import_files(paths: list[str]) -> dict:
    if not settings.db_pass:
        raise RuntimeError("未配置 DB_PASS，无法入库（请在 .env 中设置）")
    files = collect_files(paths)
    if not files:
        return {"tables": [], "total_rows": 0}

    conn = mysql.connector.connect(host=settings.db_host, port=settings.db_port, user=settings.db_user,
                                   password=settings.db_pass, database=settings.db_name)
    cur = conn.cursor()
    summary = []
    total_rows = 0
    try:
        for f in files:
            stem = os.path.splitext(os.path.basename(f))[0]
            sheets = read_csv_sheets(f) if f.lower().endswith(".csv") else read_xlsx_sheets(f)
            if not sheets:
                continue
            for sheet, grid in sheets:
                header_row, headers = detect_header(grid)
                if header_row is None:
                    continue
                used = set()
                cols = [sanitize(h, used) for h in headers]
                ncols = len(cols)
                rows = _extract_rows(grid, header_row, ncols)
                coltypes = []
                for ci in range(ncols):
                    sample = [r[ci] for r in rows if r[ci] != ""][:500]
                    coltypes.append(infer_type(sample))
                tname = table_name(stem, sheet, len(sheets), settings.table_prefix)
                coldefs = ", ".join(f"`{c}` {t}" for c, t in zip(cols, coltypes))
                ddl = f"CREATE TABLE `{tname}` (__pk BIGINT AUTO_INCREMENT PRIMARY KEY, {coldefs}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4"
                cur.execute(f"DROP TABLE IF EXISTS `{tname}`")
                cur.execute(ddl)
                placeholders = ", ".join(["%s"] * ncols)
                collist = ", ".join(f"`{c}`" for c in cols)
                sql = f"INSERT INTO `{tname}` ({collist}) VALUES ({placeholders})"
                data = [[(None if v == "" else v) for v in r] for r in rows]
                if data:
                    cur.executemany(sql, data)
                conn.commit()
                summary.append({"table": tname, "rows": len(data), "columns": ncols,
                                "source": f"{os.path.basename(f)}/{sheet}"})
                total_rows += len(data)
    finally:
        cur.close()
        conn.close()
    return {"tables": summary, "total_rows": total_rows}
