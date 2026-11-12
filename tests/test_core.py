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
