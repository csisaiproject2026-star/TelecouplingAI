"""
read_file — allows the AI to read and analyze output files (CSV, TXT, JSON, HTML).
Returns a text summary that Gemini can use for analysis and Q&A.
"""
from __future__ import annotations
import csv
import os
from pathlib import Path


MAX_ROWS = 100      # max data rows to pass to the AI
MAX_CHARS = 12000   # hard cap on total characters returned


async def run_read_file(params: dict, session_id: str, task_id: str, progress_callback) -> dict:
    """
    Read a file and return its content as text for the AI to analyze.

    Supported formats:
      - CSV  → column names, row count, and up to MAX_ROWS rows as formatted text
      - TXT  → raw text (truncated at MAX_CHARS)
      - Other → error message
    """
    progress_callback(10, "Reading file...")

    file_path = params.get("file_path", "").strip()
    if not file_path:
        raise ValueError("file_path is required")

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    suffix = Path(file_path).suffix.lower()
    filename = Path(file_path).name

    progress_callback(40, f"Parsing {suffix} file...")

    if suffix == ".csv":
        content = _read_csv(file_path, filename)
    elif suffix in (".txt", ".log", ".json"):
        content = _read_text(file_path, filename)
    elif suffix in (".html", ".htm"):
        content = _read_html(file_path, filename)
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Supported: .csv, .txt, .json, .html")

    progress_callback(100, "Done")

    return {
        "files": [],
        "content": content[:MAX_CHARS],
    }


def _read_csv(file_path: str, filename: str) -> str:
    with open(file_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return f"File: {filename}\n(empty — no data rows)"

    columns = list(rows[0].keys())
    total = len(rows)
    preview = rows[:MAX_ROWS]

    lines = [
        f"File: {filename}",
        f"Total rows: {total}",
        f"Columns ({len(columns)}): {', '.join(columns)}",
        "",
        "--- Data ---",
    ]

    # Format as aligned text table
    col_widths = {c: max(len(c), max(len(str(r.get(c, ""))) for r in preview)) for c in columns}
    header = "  ".join(c.ljust(col_widths[c]) for c in columns)
    lines.append(header)
    lines.append("-" * len(header))
    for row in preview:
        lines.append("  ".join(str(row.get(c, "")).ljust(col_widths[c]) for c in columns))

    if total > MAX_ROWS:
        lines.append(f"\n... (showing first {MAX_ROWS} of {total} rows)")

    return "\n".join(lines)


def _read_text(file_path: str, filename: str) -> str:
    with open(file_path, encoding="utf-8-sig", errors="replace") as f:
        text = f.read()
    return f"File: {filename}\n\n{text}"


def _read_html(file_path: str, filename: str) -> str:
    """Extract readable text from HTML — typically InVEST's report.html.

    Strips <script>/<style>, flattens <table> rows to "cell | cell | cell",
    and prefixes headings so the AI can still see the document structure.
    """
    from bs4 import BeautifulSoup

    with open(file_path, encoding="utf-8", errors="replace") as f:
        soup = BeautifulSoup(f, "html.parser")

    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()

    # Flatten <table> rows into pipe-separated lines so structure survives
    # plain-text extraction (InVEST reports rely heavily on tables).
    for table in soup.find_all("table"):
        rows = []
        for tr in table.find_all("tr"):
            cells = [c.get_text(" ", strip=True) for c in tr.find_all(["th", "td"])]
            if any(cells):
                rows.append(" | ".join(cells))
        table.replace_with("\n".join(rows))

    # Prefix headings so the AI can navigate sections
    for level in range(1, 7):
        for h in soup.find_all(f"h{level}"):
            prefix = "#" * level + " "
            h.insert_before(prefix)

    text = soup.get_text("\n", strip=True)
    # Collapse runs of blank lines
    lines = [ln for ln in (l.strip() for l in text.splitlines()) if ln]
    cleaned = "\n".join(lines)

    return f"File: {filename}\n\n{cleaned}"
