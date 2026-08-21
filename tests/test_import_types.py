import csv

import openpyxl

from app.import_data import infer_type, detect_header, sanitize, system_table_name, read_csv_sheets, read_xlsx_sheets, _group_by_signature


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


def test_system_table_name():
    assert system_table_name("订单", "", False) == "订单"
    assert system_table_name("订单", "明细", True) == "订单_明细"
    assert system_table_name("订单", "明细", True, prefix="exp") == "exp_订单_明细"
    assert system_table_name("2024", "", False) == "t_2024"


def test_group_by_signature():
    sheets = [
        ("Sheet1", ["a", "b"], [["1", "2"]]),
        ("Sheet2", ["a", "b"], [["3", "4"]]),   # 同结构
        ("Sheet3", ["x", "y"], [["5", "6"]]),   # 不同结构
    ]
    groups = _group_by_signature(sheets)
    assert len(groups) == 2
    assert len(groups[("a", "b")]) == 2
    assert len(groups[("x", "y")]) == 1


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
