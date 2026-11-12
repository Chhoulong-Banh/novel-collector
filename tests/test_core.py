from pathlib import Path
import pytest
from novel_collector.core import validate_url, parse_directory, collect, CollectionError

URL = "https://www.hetushu.com/book/7633/index.html"
DEMO_URL = "https://www.hetushu.com/book/999999/index.html"
HTML = (Path(__file__).parent.parent / "examples/demo.html").read_text(encoding="utf-8")

def test_url_validation():
    assert validate_url(URL) == URL
    for bad in ["http://www.hetushu.com/book/7633/index.html", "https://evil.example/book/7633/index.html", "https://www.hetushu.com/book/999999/1001.html", "https://www.hetushu.com@evil.example/book/7633/index.html"]:
        with pytest.raises(CollectionError):
            validate_url(bad)

def test_parse_ten():
    chapters = parse_directory(HTML, DEMO_URL)
    assert len(chapters) == 10
    assert chapters[0].title == "第一章 测试标题一"
    assert chapters[0].volume == "第一卷 封神之战！"
    assert chapters[-1].sequence == 10

def test_export(tmp_path):
    md, report = collect(DEMO_URL, 1, 10, out_dir=str(tmp_path), html=HTML)
    assert md.exists() and report.exists()
    assert md.read_text(encoding="utf-8").count("[Open]") == 10
    assert '"range_complete": true' in report.read_text(encoding="utf-8")

def test_deduplicate():
    duplicated = HTML.replace('</div>', '<a href="/book/999999/1001.html">第一章 重复</a></div>')
    assert len(parse_directory(duplicated, DEMO_URL)) == 10

def test_real_url_preserved_from_supplied_fixture():
    html = '<h2>第一卷 封神之战！</h2><a href="/book/7633/5339798.html">第一章 示例</a>'
    chapters = parse_directory(html, URL)
    assert len(chapters) == 1
    assert chapters[0].chapter_id == "5339798"
    assert chapters[0].url == "https://www.hetushu.com/book/7633/5339798.html"

def test_demo_output_is_separate_and_labeled(tmp_path):
    md, report = collect(DEMO_URL, 1, 10, out_dir=tmp_path, html=HTML)
    assert md.parent.name == "demo"
    assert "DEMO — NOT VERIFIED" in md.read_text(encoding="utf-8")
    import json
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["data_origin"] == "synthetic_demo"
    assert data["verified_live"] is False
    assert all("/book/7633/" not in ch["url"] for ch in data["chapters"])

def test_chapter_id_not_generated_from_position():
    html = '<a href="/book/7633/5339798.html">第一章 示例</a><a href="/book/7633/5340394.html">第二百四十九章 示例</a>'
    chapters = parse_directory(html, URL)
    assert [c.chapter_id for c in chapters] == ["5339798", "5340394"]
    assert [c.sequence for c in chapters] == [1, 2]

from novel_collector.core import validate_chapter_url, collect_url_range

def test_url_range_inclusive_offline(tmp_path):
    md, report = collect_url_range(
        "https://www.hetushu.com/book/999999/1002.html",
        "https://www.hetushu.com/book/999999/1004.html",
        out_dir=str(tmp_path), html=HTML)
    import json
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["mode"] == "chapter_url_range"
    assert [x["chapter_id"] for x in data["chapters"]] == ["1002", "1003", "1004"]
    assert data["data_origin"] == "synthetic_demo"
    assert "DEMO" in md.read_text(encoding="utf-8")

def test_url_range_missing_boundary_fails(tmp_path):
    with pytest.raises(CollectionError, match="Range unresolved"):
        collect_url_range(
            "https://www.hetushu.com/book/999999/1001.html",
            "https://www.hetushu.com/book/999999/9999.html",
            out_dir=str(tmp_path), html=HTML)

def test_url_range_reversed_fails(tmp_path):
    with pytest.raises(CollectionError, match="after end"):
        collect_url_range(
            "https://www.hetushu.com/book/999999/1004.html",
            "https://www.hetushu.com/book/999999/1002.html",
            out_dir=str(tmp_path), html=HTML)

def test_url_range_cross_novel_fails(tmp_path):
    with pytest.raises(CollectionError, match="same novel"):
        collect_url_range(
            "https://www.hetushu.com/book/999999/1001.html",
            "https://www.hetushu.com/book/7633/5340394.html",
            out_dir=str(tmp_path), html=HTML)

def test_validate_chapter_url_rejects_non_chapter():
    with pytest.raises(CollectionError):
        validate_chapter_url("https://www.hetushu.com/book/7633/index.html")

from novel_collector.washai import validate_directory as washai_directory, validate_chapter as washai_chapter, parse_page as washai_parse, collect_washai

WASHAI_INDEX = "https://book.washai.net/book/indexList-1262260513468565364.html"
WASHAI_START = "https://book.washai.net/book/1262260513468565364/2039351400477257412.html"
WASHAI_END = "https://book.washai.net/book/1262260513468565364/2039351400477257414.html"
WASHAI_HTML = (Path(__file__).parent.parent / "examples/washai_demo.html").read_text(encoding="utf-8")

def test_washai_url_validation():
    assert washai_directory("https://book.washai.net/book/1262260513468565364.html") == WASHAI_INDEX
    assert washai_chapter(WASHAI_START).endswith("2039351400477257412.html")
    with pytest.raises(CollectionError):
        washai_chapter("https://evil.example/book/1262260513468565364/123.html")

def test_washai_directory_fixture():
    chapters, pages = washai_parse(WASHAI_HTML, WASHAI_INDEX)
    assert len(chapters) == 3
    assert pages == []
    assert chapters[0].url == WASHAI_START

def test_washai_range_offline(tmp_path):
    md, report = collect_washai(start_url=WASHAI_START, end_url=WASHAI_END, html=WASHAI_HTML, out_dir=str(tmp_path))
    import json
    data = json.loads(report.read_text(encoding="utf-8"))
    assert md.name.startswith("washai-")
    assert data["source_adapter"] == "washai"
    assert data["selected_count"] == 3
    assert data["data_origin"] == "synthetic_demo"

def test_washai_missing_end_fails(tmp_path):
    with pytest.raises(CollectionError, match="Range unresolved"):
        collect_washai(start_url=WASHAI_START, end_url="https://book.washai.net/book/1262260513468565364/999999.html", html=WASHAI_HTML, out_dir=str(tmp_path))

from novel_collector.sequential import generate_candidates, export_candidates

def test_sequential_start_at_twenty():
    rows = generate_candidates(20, 30, "https://book.washai.net/book/1262260513468565364/2039351400477257431.html")
    assert len(rows) == 11
    assert rows[0]["chapter_number"] == 20
    assert rows[0]["chapter_id"] == "2039351400477257431"
    assert rows[-1]["chapter_number"] == 30
    assert rows[-1]["chapter_id"] == "2039351400477257441"
    assert all(not row["verified"] for row in rows)

def test_sequential_chapter_600():
    rows = generate_candidates(1, 600, "https://book.washai.net/book/1262260513468565364/2039351400477257412.html",
        end_url="https://book.washai.net/book/1262260513468565364/2039351400477258011.html")
    assert rows[-1]["chapter_id"] == "2039351400477258011"

def test_sequential_end_mismatch():
    with pytest.raises(CollectionError, match="End URL mismatch"):
        generate_candidates(20, 30, "https://book.washai.net/book/1262260513468565364/2039351400477257431.html",
            end_url="https://book.washai.net/book/1262260513468565364/2039351400477257999.html")

def test_sequential_rejects_other_source():
    with pytest.raises(CollectionError):
        generate_candidates(1, 3, "https://www.hetushu.com/book/7633/5339798.html")

def test_sequential_export_unverified(tmp_path):
    md, report = export_candidates(20, 21, "https://book.washai.net/book/1262260513468565364/2039351400477257431.html", out_dir=tmp_path)
    import json
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["verified_live"] is False
    assert data["data_origin"] == "calculated_unverified"
    assert data["candidate_count"] == 2
    assert "UNVERIFIED" in md.read_text(encoding="utf-8")
