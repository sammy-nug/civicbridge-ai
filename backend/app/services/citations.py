"""Turn the model's [n] markers into citations built only from retrieved metadata.

The model never supplies a title or URL. A marker that matches no evidence item is removed, so
an invented citation has nothing to point at. Numbers in an answer must appear in its evidence.
"""
from __future__ import annotations

import re
from datetime import date

from app.schemas.api import Citation
from app.services.retrieval import Evidence

MARKER = re.compile(r"\[(\d+)\]")
URL = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,:]\d+)*")
EVIDENCE_NUMBER = re.compile(r"\d+(?:[.,:]\d+)*")
EXCERPT_MAX_CHARS = 320
_SPELLED_VALUES = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
    "seventy": 70, "eighty": 80, "ninety": 90,
}
_SPELLED_SCALES = {"hundred": 100, "thousand": 1000, "million": 1000000}
_SPELLED_WORD = "|".join([*_SPELLED_VALUES, *_SPELLED_SCALES])
SPELLED_NUMBER = re.compile(
    rf"\b(?:{_SPELLED_WORD})(?:(?:\s+|-|(?:(?<=hundred)|(?<=thousand)|(?<=million))\s+and\s+)(?:{_SPELLED_WORD}))*\b",
    re.IGNORECASE,
)
# "In general," is for plain explanation. These words mean the sentence is stating an electoral fact.
ELECTORAL_FACT = re.compile(
    r"\d|\b(?:vot\w*|poll\w*|ballot\w*|elect\w*|regist\w*|pvcs?|cards?|deadlines?|penalt\w*|fines?|fees?"
    r"|offences?|candidates?|part(?:y|ies)|collat\w*|accredit\w*|bvas)\b",
    re.IGNORECASE,
)
MONTHS = ("January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December")
# Sentence-level ordinals and list numbering are not factual claims.
LIST_NUMBER = re.compile(r"(?m)^\s*\d+[.)]\s")

STATUS_NOTES = {
    "current": "",
    "needs_verification": "Official, but it predates or may not reflect the Electoral Act 2026. Details may have changed.",
    "historical": "Historical document. Do not treat as a current rule.",
    "superseded": "Replaced by a newer edition. Do not treat as a current rule.",
}
OCR_NOTE = "Text read from a scanned page; small reading errors are possible."


def extract_passage(text: str, query: str) -> str:
    """Pick the sentences in a chunk that best match the query, for display on the source card."""
    sentences = [s.strip() for s in re.split(r"(?<=[.;:])\s+|\n+", text) if len(s.strip()) > 15]
    if not sentences:
        return text[:EXCERPT_MAX_CHARS]
    query_words = {word for word in re.findall(r"\w+", query.lower()) if len(word) > 3}
    ranked = sorted(
        enumerate(sentences),
        key=lambda pair: -len(query_words & set(re.findall(r"\w+", pair[1].lower()))),
    )
    chosen, length = [], 0
    for index, sentence in ranked:
        if length + len(sentence) > EXCERPT_MAX_CHARS and chosen:
            break
        chosen.append((index, sentence))
        length += len(sentence)
    excerpt = " ".join(sentence for _, sentence in sorted(chosen))
    return excerpt if len(excerpt) <= EXCERPT_MAX_CHARS else excerpt[:EXCERPT_MAX_CHARS].rsplit(" ", 1)[0] + "…"


def strip_links(text: str) -> str:
    return re.sub(r"\s{2,}", " ", URL.sub("", text)).strip()


def spelled_numbers_to_digits(text: str) -> str:
    """Turn "seven" into "7" so a spelled-out number gets checked too. A lone "one" is left alone,
    because it is usually a plain word ("one of the documents")."""

    def convert(match: re.Match) -> str:
        words = re.findall(rf"\b(?:{_SPELLED_WORD})\b", match.group(0).lower())
        if words == ["one"]:
            return match.group(0)
        total = current = 0
        for word in words:
            if word in _SPELLED_SCALES:
                current = (current or 1) * _SPELLED_SCALES[word]
                if _SPELLED_SCALES[word] >= 1000:
                    total, current = total + current, 0
            else:
                current += _SPELLED_VALUES[word]
        return str(total + current)

    return SPELLED_NUMBER.sub(convert, text)


def remove_today_mentions(text: str, today: date) -> str:
    """The model is given today's date and may state it, as a whole date. Parts of it prove nothing:
    allowing the bare day number would let an invented "6 days" pass on the 6th of the month."""
    month, day, year = MONTHS[today.month - 1], today.day, today.year
    suffix = "th" if 11 <= day <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    mentions = [
        f"{day}{suffix} of {month} {year}", f"{day}{suffix} {month} {year}", f"{day:02d} {month} {year}",
        f"{day} {month} {year}", f"{month} {day}{suffix}, {year}", f"{month} {day}, {year}", f"{month} {day} {year}",
        today.isoformat(), f"{day:02d}/{today.month:02d}/{year}", f"{day}/{today.month}/{year}", f"{month} {year}",
    ]
    for mention in mentions:
        text = re.sub(re.escape(mention), " ", text, flags=re.IGNORECASE)
    return text


def unsupported_numbers(answer: str, cited: list[Evidence]) -> list[str]:
    """Numbers in the answer not found in the passages it cites, such as an invented fine or date.

    Evidence is scanned loosely, since OCR text may have letters touching digits ("8:30am").
    """
    body = spelled_numbers_to_digits(LIST_NUMBER.sub("", MARKER.sub(" ", answer)))
    known = set()
    for item in cited:
        known.update(number.replace(",", "") for number in EVIDENCE_NUMBER.findall(spelled_numbers_to_digits(item.text)))
    return [n for n in NUMBER.findall(body) if n.replace(",", "").rstrip(".") not in known]


def uncited_ratio(answer: str) -> float:
    """Share of sentences with no marker, ignoring ones flagged as general explanation."""
    sentences = [s for s in re.split(r"(?<=[.!?])\s+(?=[^\[\d])|\n+", answer) if len(s.strip()) > 20]
    claims = [s for s in sentences if not s.strip().lower().startswith("in general") or ELECTORAL_FACT.search(s)]
    if not claims:
        return 0.0
    return sum(1 for s in claims if not MARKER.search(s)) / len(claims)


def _passage_key(document_id: str, page: int | None, section: str | None) -> str:
    return f"{document_id}:{page}:{(section or '') if page is None else ''}"


def cited_passages(evidence: list[Evidence], citations: list[Citation]) -> list[Evidence]:
    """The evidence behind the citations: the cited page, not everything retrieved from that document."""
    keys = {_passage_key(c.document_id, c.page, c.section) for c in citations}
    return [item for item in evidence if _passage_key(item.document_id, item.page, item.section) in keys]


def build_citations(texts: list[str], evidence: list[Evidence], query: str) -> tuple[list[str], list[Citation]]:
    """Validate markers across texts, merge repeats of one page, and renumber by first use.

    Returns the rewritten texts and the citations they refer to.
    """
    numbering: dict[str, int] = {}  # document + page -> new citation number
    citations: list[Citation] = []

    def replace(match: re.Match) -> str:
        index = int(match.group(1)) - 1
        if not 0 <= index < len(evidence):
            return ""  # Invented marker: drop it.
        item = evidence[index]
        key = _passage_key(item.document_id, item.page, item.section)
        if key not in numbering:
            numbering[key] = len(numbering) + 1
            notes = [note for note in (STATUS_NOTES.get(item.status, ""), OCR_NOTE if item.extraction == "ocr" else "") if note]
            citations.append(
                Citation(
                    number=numbering[key],
                    document_id=item.document_id,
                    title=item.title,
                    organisation=item.organisation,
                    url=item.url,
                    page=item.page,
                    section=item.section or None,
                    publication_date=item.publication_date,
                    publication_date_basis=item.publication_date_basis or None,
                    retrieved_date=item.retrieved_date,
                    status=item.status,
                    notes=notes,
                    excerpt=extract_passage(item.text, query),
                    similarity=round(item.similarity, 3),
                )
            )
        return f"[{numbering[key]}]"

    rewritten = []
    for text in texts:
        # Collapse repeats such as "[1][1]" left after merging.
        result = MARKER.sub(replace, text)
        result = re.sub(r"(\[\d+\])(\s*\1)+", r"\1", result)
        rewritten.append(re.sub(r"[ \t]{2,}", " ", result).strip())
    return rewritten, citations
