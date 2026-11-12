# Novel Collector V0.3

**Sample 1 — 书海阁 (Washai)** is now the default dashboard source. **Sample 2 — 和图书 (Hetushu)** remains available. Both directory-position mode and full start/end chapter URL mode remain available.

## Washai sample

- Directory: `https://book.washai.net/book/indexList-1262260513468565364.html`
- Start: `https://book.washai.net/book/1262260513468565364/2039351400477257412.html`
- End: `https://book.washai.net/book/1262260513468565364/2039351400477258011.html`

Run the dashboard with `streamlit run app.py`, choose Washai, and start with directory positions 1–10.

The Washai adapter follows **explicit pagination links** it discovers in directory HTML (up to 20 pages by default). It does not generate chapter IDs or chapter text. It stops on HTTP 403, inaccessible robots.txt, disallowed pages, or unresolved range boundaries. Pagination selectors and live-site HTML have **not** been independently verified; unusual pagination markup may require a parser update. If only part of a directory is discovered, the requested boundary range can fail rather than silently inventing links.

Offline parser fixture:

```powershell
python -m pytest -q
python cli.py --url https://book.washai.net/book/indexList-1262260513468565364.html --start 1 --end 3 --offline-html examples/washai_demo.html
```

Offline output is marked DEMO and does not establish live-site success.

---

## Previous V0.2 documentation

Local, directory-only metadata collector with additive chapter-URL-range mode for the Hetushu novel index URL pattern. It **does not download chapter text**. Use only where permitted by website rules and applicable law.

## Requirements

Python 3.10+.

## Windows setup

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Then open http://localhost:8501 . Enter the index URL, chapter positions 1–10, and click **Discover and export directory**. Live output is written to `output/live/` and available as downloads.

## Command-line usage

```powershell
python cli.py --url https://www.hetushu.com/book/7633/index.html --start 1 --end 10 --delay 3 --output output
```

## New: full chapter URL boundaries (V0.2)\n\nThe dashboard now offers a second mode: **Start/end chapter URLs**. It retains the original directory-position mode. Both URLs must belong to the same novel, and both must appear in the accessible directory. The selected range is inclusive; intermediate IDs are never inferred numerically. If the directory returns 403 or either boundary is missing, the operation stops with a clear error. This mode exports chapter *metadata*, not chapter text.\n\n```powershell\npython cli.py --start-url https://www.hetushu.com/book/7633/5339798.html --end-url https://www.hetushu.com/book/7633/5340394.html\n```\n\nThe command requires permitted live directory access and may fail with HTTP 403.\n\n## Offline demo (no network requests)

```powershell
python cli.py --offline-html examples/demo.html --start 1 --end 10
pytest -q
```

The sample HTML uses fictional book ID `999999` and synthetic chapter IDs. Exports go to `output/demo/`, are prominently marked **DEMO — NOT VERIFIED**, and must never be treated as real Hetushu chapter links. Live results go to `output/live/`. Chapter IDs are extracted from the actual `href`, never generated from chapter numbers. The user-provided Chapter 1 URL ending in `5339798.html` is tested as a supplied fixture, not claimed to be live-verified.

## Access and safety behavior

- Only `https://www.hetushu.com/book/<id>/index.html` (or `hetushu.com`) is accepted.
- Before live retrieval, the program requests `robots.txt` and fails closed if it is inaccessible or disallows the directory.
- It does not follow redirects, bypass HTTP 403, solve CAPTCHAs, use proxies, or fetch individual chapter pages.
- A minimum 3-second interval is enforced between the robots check and directory fetch; this is not a guarantee that any given request is allowed.
- Chapter numbers are **directory positions**, not chapter numbers inferred from headings or URL IDs.
- The parser is a conservative first-pass adapter. Real-site DOM markup has not been verified because the live directory returned 403 during development. It may need selector adjustments on a legitimately accessible page.
- Volume labels are best-effort; unusual site markup may leave them empty. The report records counts and whether the requested range was fully found.
- The app does not create or push to GitHub repositories.

## Files

- `app.py`: Streamlit dashboard
- `cli.py`: command-line entry point
- `novel_collector/core.py`: validation, robots checks, parsing, export
- `examples/demo.html`: synthetic offline fixture
- `tests/test_core.py`: automated tests

## Next milestones

Improve parser against authorized real HTML; add pagination only if observed; introduce additional adapters for other sites; add job progress and resume support. Full-text collection is out of scope for V0.1.
