"""Offline candidate URL generation for Washai only; never claims verification."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse
from .core import CollectionError
from .washai import CHAPTER, HOST, validate_chapter

MAX_CANDIDATES = 10000

def generate_candidates(start_chapter: int, end_chapter: int, start_url: str,
                        increment: int = 1, end_url: str | None = None):
    """Map chapter labels to calculated URL IDs, with optional endpoint check."""
    if (not isinstance(start_chapter, int) or isinstance(start_chapter, bool)
            or not isinstance(end_chapter, int) or isinstance(end_chapter, bool)
            or start_chapter < 1 or end_chapter < start_chapter
            or end_chapter - start_chapter + 1 > MAX_CANDIDATES):
        raise CollectionError("Invalid chapter numbers or range exceeds 10,000 candidates.")
    if not isinstance(increment, int) or isinstance(increment, bool) or increment < 1:
        raise CollectionError("Increment must be a positive integer.")
    start_url = validate_chapter(start_url)
    match = CHAPTER.fullmatch(urlparse(start_url).path)
    book_id, first_id = match.group(1), int(match.group(2))
    expected_end_id = first_id + (end_chapter - start_chapter) * increment
    if end_url is not None and end_url.strip():
        end_url = validate_chapter(end_url, book_id)
        actual_end_id = int(CHAPTER.fullmatch(urlparse(end_url).path).group(2))
        if actual_end_id != expected_end_id:
            raise CollectionError(
                f"End URL mismatch: expected ID {expected_end_id}, received {actual_end_id}. "
                "Check chapter numbers, increment, or the sequential-ID assumption."
            )
    rows = [
        {"chapter_number": n, "chapter_id": str(first_id + (n - start_chapter) * increment),
         "url": f"https://{HOST}/book/{book_id}/{first_id + (n - start_chapter) * increment}.html",
         "verified": False}
        for n in range(start_chapter, end_chapter + 1)
    ]
    return rows

def export_candidates(start_chapter: int, end_chapter: int, start_url: str,
                      increment: int = 1, end_url: str | None = None, out_dir="output"):
    rows = generate_candidates(start_chapter, end_chapter, start_url, increment, end_url)
    book_id = CHAPTER.fullmatch(urlparse(validate_chapter(start_url)).path).group(1)
    folder = (Path(out_dir) / "candidates").resolve()
    folder.mkdir(parents=True, exist_ok=True)
    stem = f"washai-{book_id}-candidates-{start_chapter}-{end_chapter}"
    md, report = folder / f"{stem}.md", folder / f"{stem}.report.json"
    lines = [
        "# UNVERIFIED — Calculated chapter URL candidates", "",
        "**These URLs have NOT been checked against the website or directory.**",
        "**Chapter titles and page existence are unknown. No chapter text was retrieved.**",
        "", f"Starting chapter: {start_chapter}", f"Ending chapter: {end_chapter}",
        f"ID increment: +{increment}", "", "| Chapter | Candidate URL |",
        "|---:|---|",
    ]
    lines.extend(f"| {r['chapter_number']} | [Unverified candidate]({r['url']}) |" for r in rows)
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    data = {
        "mode": "sequential_candidates", "source_adapter": "washai",
        "data_origin": "calculated_unverified", "verified_live": False,
        "range_complete": False, "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "start_chapter": start_chapter, "end_chapter": end_chapter, "increment": increment,
        "candidate_count": len(rows), "end_url_cross_checked": bool(end_url and end_url.strip()),
        "chapters": rows,
    }
    report.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return md, report
