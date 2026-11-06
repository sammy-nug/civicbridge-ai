"""Ingestion pipeline: extract -> clean -> chunk -> embed -> store in ChromaDB.

Two stages, so deployment never needs OCR, heavy PDF tools or INEC's site being up:

  python knowledge_base/ingestion.py extract   raw_documents -> processed_documents/*.json
  python knowledge_base/ingestion.py index     processed_documents -> ChromaDB

Supported inputs: PDF (digital or scanned, via OCR), TXT and Markdown.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

KB_DIR = Path(__file__).resolve().parent
RAW_DIR = KB_DIR / "raw_documents"
PROCESSED_DIR = KB_DIR / "processed_documents"
OCR_CACHE_DIR = RAW_DIR / "ocr_cache"
sys.path.insert(0, str(KB_DIR.parent / "backend"))

CHUNK_TARGET_CHARS = 1000
CHUNK_OVERLAP_CHARS = 150
MIN_CHUNK_CHARS = 60
OCR_RENDER_SCALE = 4.0  # Lower scales lose the spaces between words in these scans.
MARGIN_NOTE_MIN_X = 0.70  # Lines starting past this page fraction are margin notes.
OCR_SAME_ROW_PIXELS = 24  # At render scale 4, about a third of a line of text.
GLUED_WORD_MIN_CHARS = 16  # Rarely a real word, so usually lost spaces.
METADATA_FIELDS = ("id", "title", "organisation", "url", "status", "publication_date",
                   "publication_date_basis", "description", "category", "extraction", "superseded_by")


@dataclass
class Page:
    number: int | None  # None for web pages and other unpaginated sources.
    text: str


# --- Step 1 and 2: load documents and extract text ------------------------------------------

def extract_digital_pdf(path: Path) -> list[Page]:
    import pypdfium2

    pdf = pypdfium2.PdfDocument(str(path))
    return [Page(i + 1, page.get_textpage().get_text_bounded()) for i, page in enumerate(pdf)]


def repair_glued_words(text: str) -> str:
    """OCR sometimes loses spaces ("Between8:00amand8:30am"). Split only clearly glued tokens."""
    import wordninja

    def repair(match: re.Match) -> str:
        token = match.group(0)
        separated = re.sub(r"(?<=[A-Za-z])(?=\d)|(?<=\d)(?=[A-Za-z])", " ", token)
        pieces = []
        for piece in separated.split(" "):
            if piece.isalpha() and len(piece) >= GLUED_WORD_MIN_CHARS:
                pieces.extend(wordninja.split(piece))
            else:
                pieces.append(piece)
        return " ".join(pieces)

    return re.sub(r"[A-Za-z0-9:]{%d,}" % GLUED_WORD_MIN_CHARS, repair, text)


def ocr_lines_to_text(lines: list[dict], page_width: float) -> str:
    """Rebuild reading order, moving margin notes out of the middle of sentences.

    Fragments on the same printed row (such as a list marker and its text) are joined left to
    right. Without this, tiny height differences put "b." on the line after its own sentence.
    """
    body, margin = [], []
    for line in sorted(lines, key=lambda item: item["y"]):
        (margin if line["x"] > page_width * MARGIN_NOTE_MIN_X else body).append(line)

    rows: list[list[dict]] = []
    for line in body:
        if rows and line["y"] - rows[-1][0]["y"] < OCR_SAME_ROW_PIXELS:
            rows[-1].append(line)
        else:
            rows.append([line])
    text = "\n".join(" ".join(part["text"] for part in sorted(row, key=lambda item: item["x"])) for row in rows)
    if margin:
        text += f"\n[Margin notes: {' '.join(part['text'] for part in margin)}]"
    return repair_glued_words(text)


def extract_scanned_pdf(path: Path, doc_id: str) -> list[Page]:
    """OCR each page. Results are cached per page because this takes ~15 seconds a page."""
    import pypdfium2
    from rapidocr_onnxruntime import RapidOCR

    OCR_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    engine, pages = None, []
    pdf = pypdfium2.PdfDocument(str(path))
    for index, page in enumerate(pdf):
        cache_file = OCR_CACHE_DIR / f"{doc_id}-{index + 1:03d}.json"
        if cache_file.exists():
            cached = json.loads(cache_file.read_text())
        else:
            engine = engine or RapidOCR()
            image = page.render(scale=OCR_RENDER_SCALE).to_numpy()
            result, _ = engine(image)
            cached = {
                "width": image.shape[1],
                "lines": [
                    {"x": min(p[0] for p in box), "y": min(p[1] for p in box), "text": text, "confidence": float(score)}
                    for box, text, score in (result or [])
                ],
            }
            cache_file.write_text(json.dumps(cached))
            print(f"  OCR {doc_id} page {index + 1}/{len(pdf)}", flush=True)
        pages.append(Page(index + 1, ocr_lines_to_text(cached["lines"], cached["width"])))
    return pages


def load_document(path: Path, doc: dict) -> list[Page]:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return extract_scanned_pdf(path, doc["id"]) if doc["extraction"] == "ocr" else extract_digital_pdf(path)
    if suffix in (".txt", ".md"):
        return [Page(None, path.read_text(encoding="utf-8"))]
    raise ValueError(f"Unsupported file type: {path.name}")


# --- Step 3: clean and normalise -------------------------------------------------------------

def normalise_text(text: str) -> str:
    replacements = {"ﬁ": "fi", "ﬂ": "fl", "’": "'", "‘": "'", "“": '"', "”": '"',
                    "­": "", "​": "", "\r": "\n", "\x02": "", "￾": "", "￿": ""}
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # Rejoin words hyphenated across lines.
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def remove_repeated_lines(pages: list[Page]) -> list[Page]:
    """Drop headers and footers: short lines that recur on many pages of a document."""
    if len(pages) < 5:
        return pages
    counts = Counter(line for page in pages for line in set(page.text.split("\n")) if len(line) < 90)
    repeated = {line for line, count in counts.items() if count >= max(4, len(pages) * 0.3)}
    for page in pages:
        page.text = "\n".join(
            line for line in page.text.split("\n") if line not in repeated and not re.fullmatch(r"\d{1,3}", line)
        )
    return pages


def is_table_of_contents(text: str) -> bool:
    """A contents page matches many queries but has no substance, so we leave it out."""
    lines = [line for line in text.split("\n") if line.strip()]
    if len(lines) < 8:
        return False
    numbered_stubs = sum(1 for line in lines if re.match(r"^\d{1,3}\.\s", line) and len(line) < 90 and not line.rstrip().endswith((".", ";", ":")))
    bare_numbers = sum(1 for line in lines if re.fullmatch(r"\d{1,3}\.", line.strip()))
    return (numbered_stubs + bare_numbers) / len(lines) > 0.35 and sum(len(line) for line in lines) / len(lines) < 70


# --- Step 4: split into meaningful chunks ----------------------------------------------------

SECTION_START = re.compile(r"^(\d{1,3})\.\s*(\(1\)|[A-Z(\"])")
HEADING = re.compile(r"^(#{1,3}\s+.+|PART [IVXLC]+\b.*|CHAPTER [IVXLC\d]+\b.*)$")


def split_into_blocks(text: str) -> list[tuple[str, str]]:
    """Return (section_label, block_text) pairs, split at legal sections and headings."""
    blocks: list[tuple[str, list[str]]] = [("", [])]
    label = ""
    for line in text.split("\n"):
        heading = HEADING.match(line)
        section = SECTION_START.match(line)
        if heading:
            label = line.lstrip("# ").strip()[:80]
            blocks.append((label, [line.lstrip("# ")]))
        elif section:
            label = f"Section/clause {section.group(1)}"
            blocks.append((label, [line]))
        else:
            blocks[-1][1].append(line)
    return [(lab, "\n".join(lines).strip()) for lab, lines in blocks if "\n".join(lines).strip()]


def split_long_block(text: str) -> list[str]:
    """Split on paragraph then sentence boundaries, with a small overlap between pieces."""
    if len(text) <= CHUNK_TARGET_CHARS:
        return [text]
    units = re.split(r"(?<=[.;:])\s+|\n\n+", text)
    pieces, current = [], ""
    for unit in units:
        if current and len(current) + len(unit) + 1 > CHUNK_TARGET_CHARS:
            pieces.append(current.strip())
            current = current[-CHUNK_OVERLAP_CHARS:]
            space = current.find(" ")
            current = current[space + 1:] if space != -1 else current
        current = f"{current} {unit}" if current else unit
    if current.strip():
        pieces.append(current.strip())
    return pieces


def chunk_pages(pages: list[Page]) -> list[dict]:
    """Group blocks into chunks of about CHUNK_TARGET_CHARS, keeping page and section labels."""
    chunks: list[dict] = []
    for page in pages:
        if is_table_of_contents(page.text):
            continue
        for label, block in split_into_blocks(page.text):
            for piece in split_long_block(block):
                previous = chunks[-1] if chunks else None
                same_page = previous is not None and previous["page"] == page.number
                short_enough = previous is not None and len(previous["text"]) + len(piece) < CHUNK_TARGET_CHARS * 0.6
                if same_page and short_enough:
                    previous["text"] += "\n" + piece  # Merge small fragments with their neighbour.
                    continue
                chunks.append({"text": piece, "page": page.number, "section": label})
    return [chunk for chunk in chunks if len(chunk["text"]) >= MIN_CHUNK_CHARS]


# --- Stage: extract --------------------------------------------------------------------------

def extract_all(only: str | None = None) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    sources = json.loads((KB_DIR / "sources.json").read_text())["documents"]
    fetch_log = json.loads((PROCESSED_DIR / "fetch_log.json").read_text())

    for doc in sources:
        if only and doc["id"] != only:
            continue
        record = fetch_log.get(doc["id"])
        if record is None:
            print(f"SKIP {doc['id']}: not fetched and verified, so it will not be ingested")
            continue
        pages = load_document(RAW_DIR / record["file"], doc)
        for page in pages:
            page.text = normalise_text(page.text)
        pages = remove_repeated_lines(pages)
        chunks = chunk_pages(pages)
        if not chunks:
            print(f"SKIP {doc['id']}: no usable text extracted")
            continue

        metadata = {field: doc.get(field) for field in METADATA_FIELDS}
        metadata["retrieved_date"] = record["retrieved_date"]
        metadata["sha256"] = record["sha256"]
        metadata["page_count"] = len(pages)
        output = {
            "document": metadata,
            "chunks": [{"chunk_id": f"{doc['id']}-{i:04d}", **chunk} for i, chunk in enumerate(chunks)],
        }
        (PROCESSED_DIR / f"{doc['id']}.json").write_text(json.dumps(output, indent=1, ensure_ascii=False))
        print(f"OK {doc['id']}: {len(pages)} pages -> {len(chunks)} chunks")


# --- Stage: index (steps 5 to 8) -------------------------------------------------------------

def index_all() -> None:
    from app.services.retrieval import get_store

    store = get_store()
    store.reset()
    total = 0
    for path in sorted(PROCESSED_DIR.glob("*.json")):
        if path.name == "fetch_log.json":
            continue
        data = json.loads(path.read_text())
        total += store.add_document(data["document"], data["chunks"])
        print(f"Indexed {path.stem}: {len(data['chunks'])} chunks", flush=True)
    print(f"Done. {total} chunks in the vector store.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=["extract", "index", "all"])
    parser.add_argument("--only", help="Extract a single document id")
    args = parser.parse_args()
    if args.stage in ("extract", "all"):
        extract_all(args.only)
    if args.stage in ("index", "all"):
        index_all()
