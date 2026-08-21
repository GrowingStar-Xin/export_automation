from app.browser import solve_captcha_svg, guess_ext


def test_solve_captcha_sorts_by_x():
    svg = '<svg><text x="30" y="0">B</text><text x="10" y="0">A</text><text x="20" y="0">C</text></svg>'
    assert solve_captcha_svg(svg) == "ACB"


def test_solve_captcha_fallback_document_order():
    svg = '<svg><tspan>A</tspan><tspan>B</tspan></svg>'
    assert solve_captcha_svg(svg) == "AB"


def test_guess_ext_from_content_type():
    assert guess_ext("application/zip", "") == "zip"
    assert guess_ext("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "") == "xlsx"
    assert guess_ext("text/csv", "") == "csv"
    assert guess_ext("application/pdf", "") == "pdf"
    assert guess_ext("application/octet-stream", "") == "bin"


def test_guess_ext_from_disposition():
    cd = "attachment; filename*=UTF-8''%E8%AE%A2%E5%8D%95.zip"
    assert guess_ext("application/octet-stream", cd) == "zip"
