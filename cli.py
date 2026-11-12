"""CLI for directory and chapter-URL-range metadata collection."""
from __future__ import annotations
import argparse
from pathlib import Path
from novel_collector.core import collect, collect_url_range, CollectionError
from novel_collector.washai import collect_washai
from novel_collector.sequential import export_candidates

def main() -> int:
    parser = argparse.ArgumentParser(description="Collect permitted directory metadata, not chapter text.")
    parser.add_argument("--url", default="https://book.washai.net/book/indexList-1262260513468565364.html")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=10)
    parser.add_argument("--start-url", help="Full starting chapter URL (requires --end-url)")
    parser.add_argument("--end-url", help="Full ending chapter URL (requires --start-url)")
    parser.add_argument("--sequential", action="store_true", help="Generate unverified Washai chapter URL candidates")
    parser.add_argument("--increment", type=int, default=1)
    parser.add_argument("--delay", type=float, default=3)
    parser.add_argument("--output", default="output")
    parser.add_argument("--offline-html", type=Path)
    args = parser.parse_args()
    if not args.sequential and bool(args.start_url) != bool(args.end_url):
        parser.error("--start-url and --end-url must be provided together")
    html = args.offline_html.read_text(encoding="utf-8") if args.offline_html else None
    if args.sequential and not args.start_url:
        parser.error("--sequential requires --start-url")
    if args.sequential and args.offline_html:
        parser.error("--sequential does not use --offline-html")
    try:
        if args.sequential:
            md, report = export_candidates(args.start, args.end, args.start_url, args.increment, args.end_url, args.output)
        elif args.start_url:
            md, report = (collect_washai(start_url=args.start_url, end_url=args.end_url, delay=args.delay, out_dir=args.output, html=html) if "book.washai.net" in args.start_url else collect_url_range(args.start_url, args.end_url, args.delay, args.output, html))
        else:
            url = args.url
            if html is not None and url == parser.get_default("url"):
                url = "https://www.hetushu.com/book/999999/index.html"
            md, report = (collect_washai(url, args.start, args.end, args.delay, args.output, html=html) if "book.washai.net" in url else collect(url, args.start, args.end, args.delay, args.output, html))
    except (CollectionError, OSError) as exc:
        parser.exit(status=1, message=f"Collection stopped: {exc}\n")
    print(f"Markdown: {md}\nReport: {report}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
