import re
from dataclasses import dataclass

ITEM_HEADING = re.compile(r"^item\s+(\d{1,2}[a-z]?)\.?\s*(.*)$", re.IGNORECASE)
SECTION_TITLES = {
    "1": "Business",
    "1a": "Risk Factors",
    "1b": "Unresolved Staff Comments",
    "1c": "Cybersecurity",
    "2": "Properties",
    "3": "Legal Proceedings",
    "4": "Mine Safety Disclosures",
    "5": "Market for Registrant's Common Equity",
    "6": "Reserved",
    "7": "Management's Discussion and Analysis",
    "7a": "Quantitative and Qualitative Disclosures About Market Risk",
    "8": "Financial Statements",
    "9": "Changes in and Disagreements with Accountants",
    "9a": "Controls and Procedures",
    "9b": "Other Information",
    "9c": "Disclosure Regarding Foreign Jurisdictions",
    "10": "Directors and Corporate Governance",
    "11": "Executive Compensation",
    "12": "Security Ownership",
    "13": "Certain Relationships and Related Transactions",
    "14": "Principal Accountant Fees and Services",
    "15": "Exhibits and Financial Statement Schedules",
    "16": "Form 10-K Summary",
}


@dataclass(frozen=True)
class FilingChunk:
    chunk_index: int
    section_title: str
    content: str


def _section_title(line: str) -> str | None:
    match = ITEM_HEADING.match(line)
    if not match:
        return None

    title = SECTION_TITLES.get(match.group(1).lower())
    if title is None:
        return None

    heading_text = match.group(2).strip().rstrip(".")
    if heading_text and len(heading_text) > 160:
        return None
    return title


def chunk_filing_text(
    text: str, *, max_words: int = 420, overlap_words: int = 60
) -> list[FilingChunk]:
    if max_words < 1 or overlap_words < 0 or overlap_words >= max_words:
        raise ValueError(
            "Chunk size must be positive and overlap smaller than the chunk"
        )

    chunks: list[FilingChunk] = []
    section_title = "Filing overview"
    section_lines: list[str] = []

    def flush_section() -> None:
        words = " ".join(section_lines).split()
        start = 0
        while start < len(words):
            end = min(start + max_words, len(words))
            chunks.append(
                FilingChunk(
                    chunk_index=len(chunks),
                    section_title=section_title,
                    content=" ".join(words[start:end]),
                )
            )
            if end == len(words):
                break
            start = end - overlap_words

    for line in text.splitlines():
        heading = _section_title(line)
        if heading is not None:
            flush_section()
            section_title = heading
            section_lines = [line]
        else:
            section_lines.append(line)
    flush_section()
    return chunks
