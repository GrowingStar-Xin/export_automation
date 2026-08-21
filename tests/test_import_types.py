import csv

import openpyxl

from app.import_data import infer_type, detect_header, sanitize, table_name, read_csv_sheets, read_xlsx_sheets


def test_infer_type():
    assert infer_type(["1", "2", "-3"]) == "BIGINT"
    assert infer_type(["1", "2.5", "3"]) == "DOUBLE"
    assert infer_type(["2026-08-20", "2026-08-21"]) == "DATE"
    assert infer_type(["2026-08-20 10:00:00"]) == "DATETIME"
    assert infer_type(["hello"]) == "VARCHAR(255)"
    assert infer_type(["x" * 300]) == "TEXT"
    assert infer_type([]) == "VARCHAR(255)"


def test_detect_header_skips_title_row():
    grid = {
        (1, "A"): "多肽合成清单", (1, "B"): "",
        (2, "A"): "序列", (2, "B"): "数量",
        (3, "A"): "AAAA", (3, "B"): "5",
        (4, "A"): "BBBB", (4, "B"): "7",
    }
    header_row, headers = detect_header(grid)
    assert header_row == 2
    assert headers == ["序列", "数量"]


def test_sanitize_dedup_and_digit_prefix():
    used = set()
    assert sanitize("序列 号", used) == "序列_号"
    assert sanitize("序列 号", used) == "序列_号_2"
    assert sanitize("2024年", used) == "c_2024年"


def test_table_name():
    assert table_name("订单", "Sheet1", 1) == "订单"
    assert table_name("订单", "明细", 2) == "订单_明细"
    assert table_name("订单", "明细", 2, prefix="exp") == "exp_订单_明细"


def test_read_csv_sheets(tmp_path):
    p = tmp_path / "a.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerows([["a", "b"], ["1", "2"]])
    sheets = read_csv_sheets(str(p))
    assert sheets[0][0] == "data"
    assert sheets[0][1][(1, "A")] == "a"


def test_read_xlsx_sheets(tmp_path):
    p = tmp_path / "a.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "明细"
    ws.append(["a", "b"])
    ws.append(["1", "2"])
    wb.save(p)
    sheets = read_xlsx_sheets(str(p))
    assert sheets[0][0] == "明细"
    assert sheets[0][1][(1, "A")] == "a"
    assert sheets[0][1][(2, "B")] == "2"
