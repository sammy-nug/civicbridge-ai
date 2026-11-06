# Responsible AI

Where possible, safeguards are enforced by code rather than left to the model's good behaviour.

| Commitment | How it's enforced | Tested in |
|---|---|---|
| No candidate or party recommendations, no persuasion | Rules run before any LLM call; the query rewrite also classifies other languages; system prompt | `test_guardrails.py`, `test_api.py` |
| No result predictions | Same | same |
| No invented procedures | Evidence-only prompt; numbers must appear in cited evidence; at least half of claim sentences must cite | `test_api.py`, `test_citations.py` |
| No invented citations | The model outputs numbers only; citations are built from stored metadata; URLs in answers are removed | `test_citations.py` |
| Abstains without evidence | No passage above the threshold means no LLM call | `test_api.py` |
| Old rules aren't presented as current | Document status; ranking penalty; warnings on cards and notices | `test_api.py`, `test_rag.py` |
| Claim checks don't accuse | Three categories only; a verdict needs valid, non-superseded citations; no evidence is never "false" | `test_api.py` |
| Minimal personal data | See [privacy.md](privacy.md) | `test_api.py` |
| Not presented as INEC | Stated in the system prompt, footer, chat input and About page | Manual |

## System prompt

All LLM instructions are in `backend/app/services/prompts.py`, in one file so they can be reviewed together.

## Language status

| Language | Human evaluation | Behaviour |
|---|---|---|
| English | Reference language | Answers are generated and validated in English |
| Hausa | **Not done** | Labelled as unreviewed everywhere it appears |
| Yoruba | **Not done** | Labelled as unreviewed everywhere it appears |
| Igbo | **Not done** | Labelled as unreviewed everywhere it appears |

The fixed messages and suggested questions in these languages were also drafted by AI and need the same review.

To mark a language as reviewed: have fluent reviewers score `evaluation/results/multilingual_review*.csv`, record who reviewed it, when, and the results here, then set `human_reviewed=True` in `backend/app/services/language.py`. A test blocks this flag until `test_no_nigerian_language_is_marked_human_reviewed` is deliberately updated.

## Known limits

- Rule-based neutrality patterns are mainly English. Other languages rely on the LLM's classification, which can fail.
- The number check catches invented numbers. It can't catch a wrong statement with no number, or a real number attached to the wrong thing.
- The language check confirms that text looks like the language. It doesn't confirm meaning.
- INEC's own pages can disagree with the law (the FAQ cites the repealed 2022 Act). Status labels were assigned by reading these documents, and need re-checking when the sources change.
- OCR text can contain errors. Citations from scanned pages say so.
- The corpus is a snapshot. Answers can miss announcements made after the retrieval date, which is shown on each citation.
