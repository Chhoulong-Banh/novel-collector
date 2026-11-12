"""Conservative directory-only collector for a supported novel index."""
from __future__ import annotations
import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup

USER_AGENT = "NovelCollectorDirectory/0.1 (+local metadata research; respects robots.txt)"
BOOK_RE = re.compile(r"^/book/(?P<book>\d+)/index\.html$")
CHAPTER_RE = re.compile(r"^/book/(?P<book>\d+)/(?P<chapter>\d+)\.html$")
VOLUME_RE = re.compile(r"^第[一二三四五六七八九十百千万零〇两\d]+[卷部篇册]")
CHAPTER_TITLE_RE = re.compile(r"第[零〇一二三四五六七八九十百千万两\d]+[章回节]")

class CollectionError(Exception):
    pass

@dataclass
class Chapter:
    sequence: int
    title: str
    url: str
    volume: str | None = None
    chapter_id: str = ""

def validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme != "https" or parsed.hostname not in {"www.hetushu.com", "hetushu.com"} or parsed.port is not None or parsed.username or parsed.password:
        raise CollectionError("Only HTTPS Hetushu book directory URLs are supported.")
    if not BOOK_RE.fullmatch(parsed.path) or parsed.query or parsed.fragment:
        raise CollectionError("Expected https://www.hetushu.com/book/<numeric-id>/index.html")
    return f"https://www.hetushu.com{parsed.path}"

def fetch_directory(url: str, delay: float = 3.0) -> str:
    url = validate_url(url)
    if delay < 3:
        raise CollectionError("Request interval must be at least 3 seconds.")
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html"})
    robots_url = "https://www.hetushu.com/robots.txt"
    try:
        robots_response = session.get(robots_url, timeout=15, allow_redirects=False)
    except requests.RequestException as exc:
        raise CollectionError(f"Could not check robots.txt; stopping safely: {exc}") from exc
    if robots_response.status_code != 200:
        raise CollectionError(f"robots.txt returned HTTP {robots_response.status_code}; stopping safely.")
    rp = RobotFileParser()
    rp.parse(robots_response.text.splitlines())
    if not rp.can_fetch(USER_AGENT, url):
        raise CollectionError("robots.txt does not permit this directory request.")
    crawl_delay = rp.crawl_delay(USER_AGENT)
    time.sleep(max(delay, float(crawl_delay or 0)))
    try:
        response = session.get(url, timeout=20, allow_redirects=False)
    except requests.RequestException as exc:
        raise CollectionError(f"Directory request failed: {exc}") from exc
    if response.status_code != 200:
        raise CollectionError(f"Directory returned HTTP {response.status_code}; no bypass attempted.")
    if "html" not in response.headers.get("Content-Type", "").lower():
        raise CollectionError("Directory did not return HTML.")
    response.encoding = response.apparent_encoding or response.encoding
    return response.text

def parse_directory(html: str, url: str) -> list[Chapter]:
    url = validate_url(url)
    book_id = BOOK_RE.fullmatch(urlparse(url).path).group("book")
    soup = BeautifulSoup(html, "html.parser")
    for node in soup(["script", "style", "nav", "footer"]):
        node.decompose()
    chapters: list[Chapter] = []
    seen: set[str] = set()
    current_volume = None
    for node in soup.find_all(["h1", "h2", "h3", "h4", "dt", "a"]):
        if node.name != "a":
            heading = node.get_text(" ", strip=True)
            if VOLUME_RE.match(heading):
                current_volume = heading
            continue
        href = node.get("href", "")
        absolute = urljoin(url, href)
        parsed = urlparse(absolute)
        if parsed.scheme != "https" or parsed.hostname not in {"www.hetushu.com", "hetushu.com"}:
            continue
        match = CHAPTER_RE.fullmatch(parsed.path)
        if not match or match.group("book") != book_id or parsed.query or parsed.fragment:
            continue
        title = node.get_text(" ", strip=True)
        if not title or not CHAPTER_TITLE_RE.search(title):
            continue
        canonical = f"https://www.hetushu.com{parsed.path}"
        if canonical in seen:
            continue
        seen.add(canonical)
        chapters.append(Chapter(len(chapters) + 1, title, canonical, current_volume, match.group("chapter")))
    return chapters

def safe_markdown(s: str) -> str:
    return s.replace("|", "\\|").replace("\n", " ").replace("\r", " ")

def export(chapters: list[Chapter], url: str, start: int, end: int, out_dir: str | Path, *, demo: bool = False) -> tuple[Path, Path]:
    if start < 1 or end < start:
        raise CollectionError("Chapter range must be positive and end >= start.")
    selected = [ch for ch in chapters if start <= ch.sequence <= end]
    if not selected:
        raise CollectionError("No chapters found in the selected range; no export produced.")
    out = (Path(out_dir) / ("demo" if demo else "live")).resolve()
    out.mkdir(parents=True, exist_ok=True)
    if urlparse(url).hostname == "book.washai.net":
        from .washai import validate_directory
        validated = validate_directory(url)
        book_id = re.fullmatch(r"/book/indexList-(\d+)\.html", urlparse(validated).path).group(1)
        base = f"washai-{book_id}-chapters-{start}-{end}"
    else:
        book_id = BOOK_RE.fullmatch(urlparse(validate_url(url)).path).group("book")
        base = f"hetushu-{book_id}-chapters-{start}-{end}"
    md_path = out / f"{base}.md"
    report_path = out / f"{base}.report.json"
    lines = ["# " + ("DEMO — NOT VERIFIED — Synthetic chapter directory" if demo else "Novel chapter directory"), "", "**DEMO DATA — NOT REAL CHAPTER LINKS**" if demo else "**LIVE DIRECTORY METADATA — NOT CHAPTER TEXT**", "", f"Source: {url}", f"Selected directory positions: {start}–{end}", "", "| Position | Volume | Chapter title | Link |", "|---:|---|---|---|"]
    for ch in selected:
        lines.append(f"| {ch.sequence} | {safe_markdown(ch.volume or '—')} | {safe_markdown(ch.title)} | [Open]({ch.url}) |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    report = {"source": url, "mode": "directory_only", "data_origin": "synthetic_demo" if demo else "live_http", "verified_live": not demo, "generated_at_utc": datetime.now(timezone.utc).isoformat(), "discovered_count": len(chapters), "selected_count": len(selected), "requested_start": start, "requested_end": end, "requested_count": end-start+1, "range_complete": len(selected) == end-start+1, "chapters": [asdict(ch) for ch in selected]}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return md_path, report_path

def collect(url: str, start: int = 1, end: int = 10, delay: float = 3, out_dir: str = "output", html: str | None = None):
    url = validate_url(url)
    if start < 1 or end < start:
        raise CollectionError("Invalid chapter range.")
    is_demo = html is not None
    if html is None:
        html = fetch_directory(url, delay)
    chapters = parse_directory(html, url)
    if not chapters:
        raise CollectionError("No matching chapter links found. Page structure may differ or access may be restricted.")
    return export(chapters, url, start, end, out_dir, demo=is_demo)

def validate_chapter_url(url: str, expected_book: str | None = None) -> str:
    """Validate a supplied full chapter URL without deriving its ID."""
    parsed = urlparse(url.strip())
    if (parsed.scheme != "https" or parsed.hostname not in {"www.hetushu.com", "hetushu.com"}
            or parsed.port is not None or parsed.username or parsed.password
            or parsed.query or parsed.fragment):
        raise CollectionError("Expected a direct HTTPS Hetushu chapter URL.")
    match = CHAPTER_RE.fullmatch(parsed.path)
    if not match:
        raise CollectionError("Expected /book/<book-id>/<chapter-id>.html")
    if expected_book is not None and match.group("book") != expected_book:
        raise CollectionError("Start and end chapter URLs must belong to the same novel.")
    return f"https://www.hetushu.com{parsed.path}"

def collect_url_range(start_url: str, end_url: str, delay: float = 3,
                      out_dir: str = "output", html: str | None = None):
    """Resolve inclusive boundary URLs against actual directory links.

    No numeric-ID guessing, chapter text retrieval, or access bypass.
    """
    start_url = validate_chapter_url(start_url)
    book_id = CHAPTER_RE.fullmatch(urlparse(start_url).path).group("book")
    end_url = validate_chapter_url(end_url, expected_book=book_id)
    directory_url = f"https://www.hetushu.com/book/{book_id}/index.html"
    demo = html is not None
    if html is None:
        html = fetch_directory(directory_url, delay)
    chapters = parse_directory(html, directory_url)
    positions = {chapter.url: chapter.sequence for chapter in chapters}
    missing = [label for label, value in (("start", start_url), ("end", end_url))
               if value not in positions]
    if missing:
        raise CollectionError(
            "Range unresolved: " + ", ".join(missing)
            + " chapter URL(s) not found in the accessible directory. "
            "No intermediate chapter IDs were generated."
        )
    start, end = positions[start_url], positions[end_url]
    if start > end:
        raise CollectionError("Start chapter appears after end chapter in directory order.")
    md_path, report_path = export(chapters, directory_url, start, end, out_dir, demo=demo)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report.update({"mode": "chapter_url_range", "start_chapter_url": start_url,
                   "end_chapter_url": end_url, "range_resolution": "directory_links"})
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return md_path, report_path
