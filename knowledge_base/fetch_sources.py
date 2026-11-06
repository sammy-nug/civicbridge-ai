"""Download every source in sources.json, verify it, and record when it was retrieved.

Nothing is assumed to exist: a source that fails to download or has the wrong content
type is reported and left out, never replaced with something else.

Usage: python knowledge_base/fetch_sources.py
"""
from __future__ import annotations

import hashlib
import html as html_lib
import json
import re
import sys
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import httpx

KB_DIR = Path(__file__).resolve().parent
RAW_DIR = KB_DIR / "raw_documents"
PROCESSED_DIR = KB_DIR / "processed_documents"
USER_AGENT = "Mozilla/5.0 (compatible; CivicBridgeAI/0.1; civic education research)"

STRING_FIELD = r'(heading|introHtml|intro|title|desc|body|offence|offense|penalty|tier|question|answer):"((?:[^"\\]|\\.)*)"'


def clean_html_to_text(raw_html: str) -> str:
    """Reduce a server-rendered page to its visible text, without nav, footer or comments."""
    text = re.sub(r"(?s)<!--.*?-->", " ", raw_html)
    text = re.sub(r"(?is)<(script|style|nav|footer|noscript|header).*?</\1>", " ", text)
    text = re.sub(r"(?i)<(br|/p|/div|/li|/h[1-6]|/tr)[^>]*>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html_lib.unescape(text)
    lines = [re.sub(r"[ \t ]+", " ", line).strip() for line in text.split("\n")]
    cookie_banner = re.compile(r"(?i)cookies? on this portal|essential cookies|cookie policy|accept all|reject all|manage preferences")
    return "\n".join(line for line in lines if line and not cookie_banner.search(line))


def js_string(value: str) -> str:
    """Decode an escaped JavaScript string literal and drop inline HTML tags."""
    try:
        value = json.loads(f'"{value}"')
    except json.JSONDecodeError:
        pass
    return re.sub(r"<[^>]+>", "", value).strip()


def find_page_bundle(client: httpx.Client, page_url: str, page_html: str, marker: str) -> str | None:
    """INEC renders tabs client-side, so their official text is in the page's JS bundle."""
    for path in sorted(set(re.findall(r"/_nuxt/[A-Za-z0-9._-]+\.js", page_html))):
        response = client.get(urljoin(page_url, path))
        if response.status_code == 200 and marker in response.text:
            return response.text
    return None


def faqs_to_markdown(bundle: str) -> str:
    pattern = r'category:"((?:[^"\\]|\\.)*)",question:"((?:[^"\\]|\\.)*)",answer:"((?:[^"\\]|\\.)*)"'
    entries = [f"## {js_string(q)}\n\nCategory: {js_string(c)}\n\n{js_string(a)}" for c, q, a in re.findall(pattern, bundle)]
    if not entries:
        raise ValueError("no FAQ entries found in page bundle")
    return "# Frequently Asked Questions (Voter FAQs)\n\n" + "\n\n".join(entries)


def education_to_markdown(bundle: str) -> str:
    """Pull the tab content (how to vote, rights, inclusion, offences, collation, thresholds)."""
    start = bundle.find('{heading:"Ste')
    end = bundle.find('{heading:"Frequently Asked Questions', start)
    if start == -1 or end == -1:
        raise ValueError("voter education content not found in page bundle")

    token = re.compile(STRING_FIELD + r'|itemsHtml:\[((?:"(?:[^"\\]|\\.)*",?)+)\]')
    parts = ["# Voter Education & Guidelines"]
    pending_title = None
    for match in token.finditer(bundle[start:end]):
        field, raw, items = match.group(1), match.group(2), match.group(3)
        if items:
            parts.extend(f"- {js_string(item)}" for item in re.findall(r'"((?:[^"\\]|\\.)*)"', items))
            continue
        value = js_string(raw)
        if not value:
            continue
        if field == "heading":
            parts.append(f"\n## {value}")
        elif field == "title":
            pending_title = value
        elif field in ("desc", "body") and pending_title:
            parts.append(f"\n{pending_title}: {value}")
            pending_title = None
        elif field in ("offence", "offense"):
            parts.append(f"\nOffence: {value}")
        elif field == "penalty":
            parts.append(f"Penalty: {value}")
        elif field != "tier":
            parts.append(f"\n{value}")
    return "\n".join(parts)


def fetch_document(client: httpx.Client, doc: dict) -> tuple[Path, bytes]:
    response = client.get(doc["url"])
    if response.status_code != 200:
        raise ValueError(f"HTTP {response.status_code}")
    content_type = response.headers.get("content-type", "")

    if doc["type"] == "pdf":
        if not response.content.startswith(b"%PDF"):
            raise ValueError(f"not a PDF (content-type {content_type})")
        return RAW_DIR / f"{doc['id']}.pdf", response.content

    if "html" not in content_type:
        raise ValueError(f"expected an HTML page, got {content_type}")
    if doc["type"] == "web_faqs":
        bundle = find_page_bundle(client, doc["url"], response.text, 'question:"')
        if bundle is None:
            raise ValueError("FAQ bundle not found")
        text = faqs_to_markdown(bundle)
    elif doc["type"] == "web_education":
        bundle = find_page_bundle(client, doc["url"], response.text, "Offences & Penalties")
        if bundle is None:
            raise ValueError("education bundle not found")
        text = education_to_markdown(bundle)
    else:
        text = f"# {doc['title']}\n\n{clean_html_to_text(response.text)}"
    return RAW_DIR / f"{doc['id']}.md", text.encode("utf-8")


def main() -> int:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    documents = json.loads((KB_DIR / "sources.json").read_text())["documents"]
    today = date.today().isoformat()
    log, failures = {}, []

    with httpx.Client(follow_redirects=True, timeout=120, headers={"User-Agent": USER_AGENT}) as client:
        for doc in documents:
            try:
                path, content = fetch_document(client, doc)
            except (httpx.HTTPError, ValueError) as error:
                failures.append(doc["id"])
                print(f"FAILED  {doc['id']}: {error}")
                continue
            path.write_bytes(content)
            log[doc["id"]] = {
                "file": path.name,
                "retrieved_date": today,
                "sha256": hashlib.sha256(content).hexdigest(),
                "bytes": len(content),
            }
            print(f"OK      {doc['id']}  {len(content):,} bytes")

    (PROCESSED_DIR / "fetch_log.json").write_text(json.dumps(log, indent=2))
    print(f"\n{len(log)} verified, {len(failures)} failed: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
