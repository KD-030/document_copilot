import re
from pathlib import Path

from bs4 import BeautifulSoup

HIDDEN_ELEMENTS = ("head", "script", "style", "noscript", "svg", "ix:hidden")
HIDDEN_STYLE = re.compile(
    r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", re.IGNORECASE
)


def parse_filing_html(path: Path) -> str:
    """Extract visible filing text while retaining line and table-cell boundaries."""
    soup = BeautifulSoup(path.read_bytes(), "html.parser")

    for element in soup.find_all(HIDDEN_ELEMENTS):
        element.decompose()

    for element in soup.find_all(True):
        if element.attrs is None:
            continue
        style = element.get("style")
        if (
            element.has_attr("hidden")
            or element.get("aria-hidden") == "true"
            or (isinstance(style, str) and HIDDEN_STYLE.search(style))
        ):
            element.decompose()

    lines: list[str] = []
    for raw_line in soup.get_text(separator="\n").splitlines():
        line = " ".join(raw_line.split())
        if line and (not lines or line != lines[-1]):
            lines.append(line)

    return "\n".join(lines)
