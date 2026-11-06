"""Ask the real pipeline one question from the terminal. Usage: ask.py "question" [language]"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.services.rag import answer_question  # noqa: E402

started = time.perf_counter()
response = answer_question(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "en", None)
print(json.dumps({
    "seconds": round(time.perf_counter() - started, 1), "status": response.evidence_status,
    "answered_in": response.answered_in, "answer": response.answer, "notices": response.notices,
    "citations": [f"[{c.number}] {c.document_id} p.{c.page} ({c.status})" for c in response.citations],
}, indent=1, ensure_ascii=False))
