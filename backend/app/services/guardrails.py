"""Rule-based safeguards that run before any LLM call, so they hold even if a model misbehaves."""
from __future__ import annotations

import re

_GROUP = r"(?=[A-Z]*\d)[A-Z0-9]{4}"  # A 4-character group containing at least one digit.

SENSITIVE_PATTERNS = [
    # Voter Identification Numbers: 19 alphanumeric characters, often printed in groups.
    ("voter_id", re.compile(r"\b(?=[A-Z]*\d)[A-Z0-9]{19}\b", re.IGNORECASE)),
    ("voter_id_grouped", re.compile(rf"\b{_GROUP}[ -]{_GROUP}[ -]{_GROUP}[ -]{_GROUP}[ -][A-Z0-9]{{3}}\b", re.IGNORECASE)),
    # An identity label followed by a value that actually contains a digit. This leaves
    # questions such as "what is my NIN used for?" alone.
    ("id_number_context", re.compile(
        r"\b(?:vin|nin|bvn|pvc\s*(?:number|no\.?|#)|voter(?:'s)?\s*(?:id|number)|national\s+id(?:entification)?(?:\s+number)?)"
        r"\s*(?:number\s*)?(?:is|are|:|=|-)?\s*(?:[A-Z]*\d[A-Z0-9]*[ -]?)+", re.IGNORECASE)),
    ("phone", re.compile(r"(?<!\d)(?:\+?234[ -]?|0)[789][01]\d[ -]?\d{3}[ -]?\d{4}(?!\d)")),
    ("long_number", re.compile(r"\b\d{10,}\b")),
    ("email", re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")),
    ("password", re.compile(r"\b(?:password|passcode|pin)\s*(?:is|:|=)\s*\S+", re.IGNORECASE)),
]

PARTISAN_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in (
    r"\bwho\s+(?:should|shall|do you think i should|must)\s+(?:i|we|people|nigerians)\s+vote",
    r"\b(?:which|what)\s+(?:party|candidate|politician)\s+(?:should|is\s+(?:the\s+)?(?:best|better|good)|deserves)",
    r"\bshould\s+(?:i|we)\s+vote\s+(?:for|against)\b",
    r"\bbest\s+(?:candidate|party|president|presidential candidate|governor)\b",
    r"\b(?:recommend|endorse|suggest)\s+(?:me\s+)?(?:a\s+|the\s+)?(?:candidate|party)\b",
    r"\b(?:is|are)\s+\w+\s+(?:party\s+)?better\s+than\b.*\b(?:party|candidate)\b",
    r"^\s*(?:please\s+|can you\s+|help me\s+)*(?:write|create|draft|make|generate)\b.*\b(?:campaign|slogan|propaganda|persuade|convince)\b",
    r"\bconvince\s+(?:me|people|voters)\b",
)]

PREDICTION_PATTERNS = [re.compile(pattern, re.IGNORECASE) for pattern in (
    r"\bwho\s+(?:will|would|is going to|is likely to|might)\s+win\b",
    r"\b(?:predict|forecast)\b.*\b(?:election|result|winner|vote|poll)",
    r"\b(?:which|what)\s+(?:party|candidate)\s+(?:will|is going to|is likely to)\s+win\b",
    r"\bwinner\s+of\s+the\s+\d{4}\b",
)]


def scrub_sensitive(text: str) -> tuple[str, bool]:
    """Remove identity details. Returns the cleaned text and whether anything was removed."""
    removed = False
    for _name, pattern in SENSITIVE_PATTERNS:
        text, count = pattern.subn("[removed]", text)
        removed = removed or count > 0
    return text, removed


def classify_policy(text: str) -> str | None:
    """Return 'partisan' or 'prediction' if a request breaks neutrality rules, otherwise None."""
    if any(pattern.search(text) for pattern in PREDICTION_PATTERNS):
        return "prediction"
    if any(pattern.search(text) for pattern in PARTISAN_PATTERNS):
        return "partisan"
    return None
