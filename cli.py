"""Command-line entry point for directory metadata collection."""
from __future__ import annotations
import argparse
from pathlib import Path
from novel_collector.core import collect, CollectionError

def main() -> int:
    parser = argparse.ArgumentParser(description="Collect permitted directory metadata, not chapter text.")
    parser.add_argument("--url", default="https://www.hetushu.com/book/7633/index.html")
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--end", type=int, default=10)
    parser.add_argument("--delay", type=float, default=3)
    parser.add_argument("--output", default="output")
    parser.add_argument("--offline-html", type=Path)
    args = parser.parse_args()
    html = None
    if args.offline_html:
        html = args.offline_html.read_text(encoding="utf-8")
        if args.url == parser.get_default("url"):
            args.url = "https://www.hetushu.com/book/999999/index.html"
    try:
        md, report = collect(args.url, args.start, args.end, args.delay, args.output, html)
    except (CollectionError, OSError) as exc:
        parser.exit(status=1, message=f"Collection stopped: {exc}\n")
    print(f"Markdown: {md}\nReport: {report}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
