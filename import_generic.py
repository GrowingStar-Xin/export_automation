#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
通用表格入库：把任意 xlsx / csv（或 zip 包）里的每个 sheet 导入 MySQL 为独立表。
- 自动识别表头行（前 10 行中非空单元格最多的那一行）
- 自动推断列类型（BIGINT / DOUBLE / DATE / DATETIME / VARCHAR / TEXT）
- 表名 = 文件名_工作表名（可加 TABLE_PREFIX 前缀）
- 默认「替换模式」：先 DROP 再 CREATE（干净重导）；设 APPEND=1 则追加不删

用法：
  python3 import_generic.py <文件或目录或zip> [更多文件...]

环境变量：
  DB_HOST=127.0.0.1  DB_PORT=3307  DB_USER=root  DB_PASS=root123456  DB_NAME=peptide_orders
  TABLE_PREFIX=xxx   APPEND=1
"""
import os, sys, re, glob, csv, zipfile, io, tempfile, shutil
import xml.etree.ElementTree as ET
import mysql.connector

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
REL_NS = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'

DB_HOST = os.environ.get('DB_HOST', '127.0.0.1')
DB_PORT = int(os.environ.get('DB_PORT', '3307'))
DB_USER = os.environ.get('DB_USER', 'root')
DB_PASS = os.environ.get('DB_PASS', 'root123456')
DB_NAME = os.environ.get('DB_NAME', 'peptide_orders')
TABLE_PREFIX = os.environ.get('TABLE_PREFIX', '').strip()
APPEND = os.environ.get('APPEND', '') == '1'

INT_RE = re.compile(r'^-?\d+$')
FLOAT_RE = re.compile(r'^-?(\d+\.\d*|\.\d+|\d+[eE][+-]?\d+|\d+\.\d+[eE][+-]?\d+)$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
DT_RE = re.compile(r'^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}(:\d{2})?$')


def col_to_num(s):
    n = 0
    for ch in s.upper():
        n = n * 26 + (ord(ch) - 64)
    return n


def col_letter(n):
    s = ''
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def read_xlsx_sheets(path):
    """把 xlsx 所有 sheet 读成 [(sheet名, {(r,col):值})]"""
    z = zipfile.ZipFile(path)
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        root = ET.fromstring(z.read('xl/sharedStrings.xml'))
        for si in root.findall(f'{NS}si'):
            shared.append(''.join(t.text or '' for t in si.iter(f'{NS}t')))

    sheets = []
    if 'xl/workbook.xml' in z.namelist():
        wb = ET.fromstring(z.read('xl/workbook.xml'))
        for s in wb.findall(f'{NS}sheets'):
            for sh in s.findall(f'{NS}sheet'):
                sheets.append((sh.get('name'), sh.get(f'{REL_NS}id')))

    rels = {}
    if 'xl/_rels/workbook.xml.rels' in z.namelist():
        rr = ET.fromstring(z.read('xl/_rels/workbook.xml.rels'))
        for rel in rr.findall(f'{REL_NS}Relationship'):
            rels[rel.get('Id')] = rel.get('Target')

    result = []
    for name, rid in sheets:
        target = rels.get(rid, 'worksheets/sheet1.xml')
        if not target.startswith('xl/'):
            target = 'xl/' + target.lstrip('/')
        if target not in z.namelist():
            cand = 'xl/worksheets/' + target.split('/')[-1]
            target = cand if cand in z.namelist() else target
        if target not in z.namelist():
            continue
        root = ET.fromstring(z.read(target))
        grid = {}
        for row in root.iter(f'{NS}row'):
            r = int(row.get('r'))
            for c in row.findall(f'{NS}c'):
                ref = c.get('r') or ''
                col = ''.join(ch for ch in ref if ch.isalpha())
                t = c.get('t')
                val = ''
                if t == 'inlineStr':
                    val = ''.join(x.text or '' for x in c.iter(f'{NS}t'))
                else:
                    v = c.find(f'{NS}v')
                    if v is not None and v.text is not None:
                        val = v.text
                        if t == 's' and val != '':
                            try:
                                val = shared[int(val)]
                            except Exception:
                                pass
                grid[(r, col)] = val
        result.append((name, grid))
    return result


def read_csv_sheets(path):
    with open(path, newline='', encoding='utf-8-sig', errors='replace') as f:
        rows = list(csv.reader(f))
    grid = {}
    for ri, row in enumerate(rows, start=1):
        for ci, val in enumerate(row, start=1):
            grid[(ri, col_letter(ci))] = val
    return [('data', grid)]


def detect_header(grid):
    rows = sorted(set(r for (r, c) in grid))

    def cnt(r):
        return sum(1 for (rr, c), v in grid.items() if rr == r and str(v).strip() != '')

    # 表头 = 前 10 行中「非空最多 + 后面紧跟数据行」得分最高者（title/元信息行下面通常没数据）
    best_r, best_score = None, -1
    for r in rows[:10]:
        c = cnt(r)
        following = sum(1 for rr in (r + 1, r + 2, r + 3) if cnt(rr) >= 1)
        score = c * 10 + following
        if score > best_score:
            best_r, best_score = r, score
    if best_r is None or cnt(best_r) < 2:
        return None, []
    cols = sorted(col_to_num(c) for (rr, c) in grid if rr == best_r and str(grid[(rr, c)]).strip() != '')
    maxc = max(cols)
    headers = [str(grid.get((best_r, col_letter(cn)), '')).strip() or f'col_{cn}' for cn in range(1, maxc + 1)]
    return best_r, headers


def sanitize(name, used):
    n = re.sub(r'[^\w\u4e00-\u9fff]+', '_', str(name).strip(), flags=re.UNICODE)
    n = re.sub(r'_+', '_', n).strip('_')
    if not n:
        n = 'col'
    if n[0].isdigit():
        n = 'c_' + n
    n = n[:60]
    base, i = n, 2
    while n.lower() in used:
        n = f'{base}_{i}'
        i += 1
    used.add(n.lower())
    return n


def infer_type(vals):
    if not vals:
        return 'VARCHAR(255)'
    if all(INT_RE.match(v) for v in vals):
        return 'BIGINT'
    if all(INT_RE.match(v) or FLOAT_RE.match(v) for v in vals):
        return 'DOUBLE'
    if all(DATE_RE.match(v) for v in vals):
        return 'DATE'
    if all(DT_RE.match(v) for v in vals):
        return 'DATETIME'
    maxlen = max(len(v) for v in vals)
    return 'TEXT' if maxlen > 255 else 'VARCHAR(255)'


def extract_rows(grid, header_row, ncols):
    rows = []
    maxr = max(r for (r, c) in grid)
    for r in range(header_row + 1, maxr + 1):
        vals = [str(grid.get((r, col_letter(cn)), '')).strip() for cn in range(1, ncols + 1)]
        if any(v != '' for v in vals):
            rows.append(vals)
    return rows


def table_name(file_stem, sheet, total_sheets):
    def clean(s):
        s = re.sub(r'[^\w\u4e00-\u9fff]+', '_', s, flags=re.UNICODE)
        s = re.sub(r'_+', '_', s).strip('_')
        return s or 't'
    parts = [clean(file_stem)]
    if not (total_sheets == 1 and re.match(r'^sheet\d+$', sheet, re.I)):
        parts.append(clean(sheet))
    name = '_'.join(parts)
    if name[0].isdigit():
        name = 't_' + name
    name = name[:60]
    return (TABLE_PREFIX + '_' + name) if TABLE_PREFIX else name


TEMP_DIRS = []


def collect_files(args):
    files = []
    for a in args:
        if os.path.isdir(a):
            files += sorted(glob.glob(os.path.join(a, '*.xlsx')) + glob.glob(os.path.join(a, '*.xls')) + glob.glob(os.path.join(a, '*.csv')))
        elif a.lower().endswith('.zip'):
            dest = tempfile.mkdtemp(prefix='xlsx_import_')
            TEMP_DIRS.append(dest)
            with zipfile.ZipFile(a) as z:
                z.extractall(dest)
            files += sorted(glob.glob(os.path.join(dest, '**', '*.xlsx'), recursive=True)
                            + glob.glob(os.path.join(dest, '**', '*.xls'), recursive=True)
                            + glob.glob(os.path.join(dest, '**', '*.csv'), recursive=True))
        elif a.lower().endswith(('.xlsx', '.xls', '.csv')):
            files.append(a)
    # 去重保持顺序
    seen, out = set(), []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def main():
    files = collect_files(sys.argv[1:])
    if not files:
        print('未找到可导入的 xlsx/csv 文件')
        sys.exit(1)

    conn = mysql.connector.connect(host=DB_HOST, port=DB_PORT, user=DB_USER,
                                   password=DB_PASS, database=DB_NAME)
    cur = conn.cursor()

    summary = []
    total_rows = 0
    for f in files:
        stem = os.path.splitext(os.path.basename(f))[0]
        if f.lower().endswith('.csv'):
            sheets = read_csv_sheets(f)
        else:
            sheets = read_xlsx_sheets(f)
        if not sheets:
            print(f'[跳过] {f}：无法解析（无 sheet）')
            continue

        for sheet, grid in sheets:
            header_row, headers = detect_header(grid)
            if header_row is None:
                print(f'[跳过] {os.path.basename(f)}/{sheet}：未识别到表头')
                continue
            used = set()
            cols = [sanitize(h, used) for h in headers]
            ncols = len(cols)
            rows = extract_rows(grid, header_row, ncols)

            # 类型推断：取每列非空样本
            coltypes = []
            for ci in range(ncols):
                sample = [r[ci] for r in rows if r[ci] != ''][:500]
                coltypes.append(infer_type(sample))

            tname = table_name(stem, sheet, len(sheets))
            coldefs = ', '.join(f'`{c}` {t}' for c, t in zip(cols, coltypes))
            ddl = f'CREATE TABLE `{tname}` (__pk BIGINT AUTO_INCREMENT PRIMARY KEY, {coldefs}) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4'

            if not APPEND:
                cur.execute(f'DROP TABLE IF EXISTS `{tname}`')
            cur.execute(ddl)

            # 插入（空值一律 NULL）
            placeholders = ', '.join(['%s'] * ncols)
            collist = ', '.join(f'`{c}`' for c in cols)
            sql = f'INSERT INTO `{tname}` ({collist}) VALUES ({placeholders})'
            data = [[(None if v == '' else v) for v in r] for r in rows]
            if data:
                cur.executemany(sql, data)
            conn.commit()

            summary.append({'table': tname, 'rows': len(data), 'columns': ncols, 'source': f'{os.path.basename(f)}/{sheet}'})
            total_rows += len(data)
            print(f'[导入] {tname}  {len(data)} 行 × {ncols} 列  <- {os.path.basename(f)}/{sheet}')

    print(f'\n[完成] 共导入 {len(summary)} 张表 / {total_rows} 行')
    import json
    print('__SUMMARY__ ' + json.dumps({'tables': summary, 'totalRows': total_rows}, ensure_ascii=False))
    for d in TEMP_DIRS:
        shutil.rmtree(d, ignore_errors=True)
    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
