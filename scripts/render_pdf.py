#!/usr/bin/env python3
"""Render an HTML brief to an A4 PDF and check it is exactly one page.

Usage:
    python3 scripts/render_pdf.py <input.html> [output.pdf]

Exit codes:
    0  rendered, exactly one page
    1  rendered, but the page count is not 1 (cut words and re-render)
    2  usage or rendering error

Requires: pip install playwright && python3 -m playwright install chromium
Optional: pip install pypdf (more reliable page count; a byte-level fallback is used otherwise)
"""

import re
import sys
from pathlib import Path


def count_pages(pdf_path: Path) -> int:
    try:
        from pypdf import PdfReader

        return len(PdfReader(str(pdf_path)).pages)
    except ImportError:
        data = pdf_path.read_bytes()
        return len(re.findall(rb"/Type\s*/Page(?![a-zA-Z])", data))


def render(html_path: Path, pdf_path: Path) -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit(
            "playwright is not installed. Run:\n"
            "  pip install playwright\n"
            "  python3 -m playwright install chromium"
        )

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        try:
            # networkidle lets web fonts load; fall back to local fonts if offline.
            page.goto(html_path.resolve().as_uri(), wait_until="networkidle", timeout=20000)
        except Exception:
            page.goto(html_path.resolve().as_uri(), wait_until="load")
        page.evaluate("document.fonts.ready")
        page.emulate_media(media="print")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            print_background=True,
            prefer_css_page_size=True,  # honour @page margins in the template
        )
        browser.close()


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print(__doc__.strip(), file=sys.stderr)
        return 2

    html_path = Path(sys.argv[1])
    if not html_path.is_file():
        print(f"Not found: {html_path}", file=sys.stderr)
        return 2
    pdf_path = Path(sys.argv[2]) if len(sys.argv) == 3 else html_path.with_suffix(".pdf")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        render(html_path, pdf_path)
    except Exception as exc:  # noqa: BLE001 — report any rendering failure plainly
        print(f"Render failed: {exc}", file=sys.stderr)
        return 2

    pages = count_pages(pdf_path)
    if pages != 1:
        print(
            f"FAIL: {pdf_path} has {pages} pages; the brief must be exactly 1. "
            "Cut words (keep body text at 9pt or more) and re-render.",
            file=sys.stderr,
        )
        return 1

    print(f"OK: {pdf_path} (1 page)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
