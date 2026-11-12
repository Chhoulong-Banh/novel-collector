"""Washai (书海阁) directory metadata adapter. Does not retrieve chapter text."""
from __future__ import annotations
import json
import re
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
import requests
from bs4 import BeautifulSoup
from .core import Chapter, CollectionError, CHAPTER_TITLE_RE, VOLUME_RE, export

HOST = "book.washai.net"
INDEX = re.compile(r"^/book/indexList-(\d+)\.html$")
BOOK = re.compile(r"^/book/(\d+)\.html$")
CHAPTER = re.compile(r"^/book/(\d+)/(\d+)\.html$")
UA = "NovelCollectorDirectory/0.3 (metadata only; respects robots.txt)"

def _parts(url):
    p = urlparse(url.strip())
    if (p.scheme != "https" or p.hostname != HOST or p.port is not None
            or p.username or p.password or p.fragment):
        raise CollectionError("Expected a direct HTTPS book.washai.net URL.")
    return p

def validate_directory(url):
    p = _parts(url)
    if p.query:
        raise CollectionError("Directory URL must not include query parameters.")
    m = INDEX.fullmatch(p.path) or BOOK.fullmatch(p.path)
    if not m:
        raise CollectionError("Expected /book/indexList-<id>.html or /book/<id>.html")
    return f"https://{HOST}/book/indexList-{m.group(1)}.html"

def validate_chapter(url, book_id=None):
    p = _parts(url)
    if p.query:
        raise CollectionError("Chapter URL must not include query parameters.")
    m = CHAPTER.fullmatch(p.path)
    if not m or (book_id is not None and m.group(1) != book_id):
        raise CollectionError("Expected a Washai chapter URL for the same novel.")
    return f"https://{HOST}{p.path}"

def _page_link(url, book_id):
    """Only follow pagination links explicitly present in directory HTML."""
    p = _parts(url)
    if p.path == f"/book/indexList-{book_id}.html" and not p.query:
        return f"https://{HOST}{p.path}"
    if p.path == f"/book/indexList-{book_id}.html" and re.fullmatch(r"(?:page|p)=\d+", p.query):
        return f"https://{HOST}{p.path}?{p.query}"
    if re.fullmatch(rf"/book/indexList-{book_id}-\d+\.html", p.path) and not p.query:
        return f"https://{HOST}{p.path}"
    return None

def parse_page(html, directory_url):
    directory_url = validate_directory(directory_url)
    book_id = INDEX.fullmatch(urlparse(directory_url).path).group(1)
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    chapters, seen, pages = [], set(), set()
    volume = None
    for tag in soup.find_all(["h1", "h2", "h3", "h4", "dt", "a"]):
        title = tag.get_text(" ", strip=True)
        if tag.name != "a":
            if VOLUME_RE.match(title):
                volume = title
            continue
        href = urljoin(directory_url, tag.get("href", ""))
        try:
            p = _parts(href)
        except CollectionError:
            continue
        m = CHAPTER.fullmatch(p.path)
        if m and m.group(1) == book_id and not p.query and CHAPTER_TITLE_RE.search(title):
            canonical = f"https://{HOST}{p.path}"
            if canonical not in seen:
                chapters.append(Chapter(len(chapters) + 1, title, canonical, volume, m.group(2)))
                seen.add(canonical)
        elif title and (title.isdigit() or any(k in title for k in ("下一页", "上一页", "末页", "尾页", "首页", "下页", "上页"))):
            candidate = _page_link(href, book_id)
            if candidate and candidate != directory_url:
                pages.add(candidate)
    return chapters, sorted(pages)

def _request(session, url):
    try:
        response = session.get(url, timeout=20, allow_redirects=False)
    except requests.RequestException as exc:
        raise CollectionError(f"Request failed: {exc}") from exc
    if response.status_code != 200:
        raise CollectionError(f"HTTP {response.status_code} for {url}; no bypass attempted.")
    if "html" not in response.headers.get("Content-Type", "").lower():
        raise CollectionError("Expected HTML response.")
    response.encoding = response.apparent_encoding or response.encoding
    return response.text

def fetch_pages(directory_url, delay=3, max_pages=20):
    directory_url = validate_directory(directory_url)
    if delay < 3 or max_pages < 1 or max_pages > 50:
        raise CollectionError("Minimum delay is 3 seconds; max_pages must be 1–50.")
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "text/html"})
    robots_url = f"https://{HOST}/robots.txt"
    try:
        robots = session.get(robots_url, timeout=15, allow_redirects=False)
    except requests.RequestException as exc:
        raise CollectionError(f"Could not check robots.txt: {exc}") from exc
    if robots.status_code != 200:
        raise CollectionError(f"robots.txt returned HTTP {robots.status_code}; stopping.")
    rules = RobotFileParser()
    rules.parse(robots.text.splitlines())
    book_id = INDEX.fullmatch(urlparse(directory_url).path).group(1)
    queue, visited, all_chapters, seen = [directory_url], set(), [], set()
    while queue:
        if len(visited) >= max_pages:
            raise CollectionError("Pagination limit reached; refusing incomplete export.")
        url = queue.pop(0)
        if url in visited:
            continue
        if not rules.can_fetch(UA, url):
            raise CollectionError(f"robots.txt disallows {url}")
        time.sleep(max(delay, float(rules.crawl_delay(UA) or 0)))
        html = _request(session, url)
        visited.add(url)
        found, next_pages = parse_page(html, directory_url)
        for chapter in found:
            if chapter.url not in seen:
                seen.add(chapter.url)
                chapter.sequence = len(all_chapters) + 1
                all_chapters.append(chapter)
        for candidate in next_pages:
            if candidate not in visited and candidate not in queue and _page_link(candidate, book_id):
                queue.append(candidate)
    return all_chapters

def collect_washai(directory_url=None, start=1, end=10, delay=3, out_dir="output",
                   start_url=None, end_url=None, html=None):
    if (start_url is None) != (end_url is None):
        raise CollectionError("Both start and end chapter URLs are required.")
    if start_url is not None:
        start_url = validate_chapter(start_url)
        book_id = CHAPTER.fullmatch(urlparse(start_url).path).group(1)
        end_url = validate_chapter(end_url, book_id)
        directory_url = f"https://{HOST}/book/indexList-{book_id}.html"
    else:
        if not directory_url:
            raise CollectionError("Provide a directory URL.")
        directory_url = validate_directory(directory_url)
    if html is None:
        chapters = fetch_pages(directory_url, delay)
    else:
        chapters, pages = parse_page(html, directory_url)
        if pages:
            raise CollectionError("Offline fixture has pagination; cannot claim complete range.")
    if start_url is not None:
        positions = {c.url: c.sequence for c in chapters}
        if start_url not in positions or end_url not in positions:
            raise CollectionError("Range unresolved: boundary URL absent from discovered directory.")
        start, end = positions[start_url], positions[end_url]
        if start > end:
            raise CollectionError("Start chapter follows end chapter.")
    md, report = export(chapters, directory_url, start, end, out_dir, demo=html is not None)
    data = json.loads(report.read_text(encoding="utf-8"))
    data.update({"source_adapter": "washai", "mode": "chapter_url_range" if start_url else "directory_only"})
    if start_url:
        data.update({"start_chapter_url": start_url, "end_chapter_url": end_url})
    report.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return md, report
