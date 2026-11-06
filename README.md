# CivicBridge AI

**Making Electoral Information Understandable and Accessible to Every Nigerian.**

An AI civic information assistant that answers questions about Nigerian elections from official documents, with a checkable source for every fact, and says so when it can't verify something. Built for the AI4Elections Hackathon (Rise Networks), in the Inclusive and Multilingual Electoral & Civic Technology track.

> Independent project. Not affiliated with INEC or any political party. AI can make mistakes: confirm important details with INEC.

## The problem

Nigerians with simple questions about voting often have to search long legal documents and several websites to answer them. Language barriers, limited digital access and misinformation make it harder.

Accuracy here depends on timing as well as facts. While building this we found that:

- INEC's registration portal says the **CVR exercise has ended**, so "how do I register?" can't be answered with an old how-to guide.
- The **Electoral Act 2026** requires PVC replacement applications at least **90 days** before polling day, while INEC's 2013 guidelines said 7.
- INEC's live FAQ gives a vote-buying penalty of ₦500,000 under the repealed 2022 Act, while **section 22 of the 2026 Act** says not less than ₦5,000,000 or not less than two years.

A general chatbot could easily get all three wrong, and confidently. CivicBridge AI is designed around this problem.

## Solution and features

- **Ask CivicBridge:** natural conversation with follow-ups and source cards that link to the exact PDF page.
- **Check Electoral Information:** compares a statement with official sources and returns *supported*, *contradicted* or *insufficient evidence*. Not finding something is never treated as false.
- **Resources:** a searchable list of each document used, with dates and status.
- **Four languages:** English, Hausa, Yoruba and Igbo. The three Nigerian languages **have not yet passed human evaluation** and are labelled as such. A translation that fails automatic checks is replaced by the English answer with a notice.
- **Safeguards in code:** neutrality rules, removal of identity details, citation and number validation, rate limiting.
- **Accessible and light:** mobile first, keyboard navigable, about 74 KB of gzipped JS and CSS, with a data saver mode.

**Target users:** first-time and registered voters, young Nigerians, people with limited digital literacy, speakers of Nigerian languages, and civic education organisations and researchers.

## How it works

```
Question -> remove identity details -> neutrality rules -> standalone English search query
  -> retrieve passages (threshold, prefer current documents, add time-critical notices)
       nothing relevant? -> abstain, with no AI call
  -> AI answers from numbered passages only, citing them as [1], [2]
  -> validate: citations must exist, numbers must appear in the evidence
       fails? -> abstain rather than show a weak answer
  -> translate if needed, and check the translation
       fails? -> English answer with a notice
  -> answer + citations built from stored metadata (the AI never writes a URL)
```

Details and a diagram are in [docs/architecture.md](docs/architecture.md).

## Technology

| Layer | Stack |
|---|---|
| Frontend | React, Vite, Tailwind CSS, React Router, Lucide |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| RAG | Custom pipeline, ChromaDB, `all-MiniLM-L6-v2` through Sentence Transformers or ONNX |
| LLM | Gemini, or any OpenAI-compatible API (Ollama, Groq and others) |
| Storage | SQLite (response records and feedback), ChromaDB (embeddings) |
| Ingestion | pypdfium2, RapidOCR for scanned PDFs |

## Data sources

17 documents and page snapshots verified and retrieved from INEC's official sites on 2026-11-05, including the Electoral Act 2026 and the 2026 Regulations and Guidelines. Each has a status:

| Status | Meaning |
|---|---|
| `current` | The latest official information we hold |
| `needs_verification` | Official, but predates or may not reflect the 2026 Act |
| `historical`, `superseded` | Kept for reference, and never presented as today's rule |

The full list, with reasons for each exclusion, is in [knowledge_base/sources.json](knowledge_base/sources.json).

## Run it locally

Requires Python 3.12 and Node 18 or later.

```bash
# Backend
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt          # add requirements-dev.txt for tests and OCR
cp .env.example .env                               # then add your GEMINI_API_KEY
cd .. && backend/.venv/bin/python knowledge_base/ingestion.py index    # about 1 to 3 minutes
cd backend && .venv/bin/uvicorn app.main:app --reload --port 8000

# Frontend, in a second terminal
cd frontend
npm install
cp .env.example .env
npm run dev                                        # http://localhost:5173
```

### Environment variables

Documented in [backend/.env.example](backend/.env.example). The main ones:

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `gemini` or `openai_compatible` |
| `LLM_MODEL` | For example `gemini-3.6-flash` |
| `GEMINI_API_KEY` | Free from [Google AI Studio](https://aistudio.google.com/apikey) |
| `OPENAI_COMPATIBLE_BASE_URL` | For example `http://localhost:11434/v1` for Ollama |
| `EMBEDDING_BACKEND` | `onnx` (light) or `sentence_transformers` |
| `ALLOWED_ORIGINS` | Frontend URLs allowed to call the API |

Without a key, the app says the AI service isn't set up. It never shows a made-up answer.

### Refresh or add documents

Processed documents are committed, so this is only needed when sources change. It requires `requirements-dev.txt`:

```bash
backend/.venv/bin/python knowledge_base/fetch_sources.py    # download + verify
backend/.venv/bin/python knowledge_base/ingestion.py all    # extract + chunk + index
```

PDF, TXT and Markdown are supported. Add an entry to `sources.json` to include a new source.

## Tests

```bash
cd backend && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest tests ../evaluation -q     # no API key needed
```

Measured results are in [evaluation/REPORT.md](evaluation/REPORT.md), and [evaluation/README.md](evaluation/README.md) explains how to read them.

## Deployment

Frontend on Vercel, backend on Render: see [docs/deployment.md](docs/deployment.md).

## Limitations

- **Answer quality with Gemini still needs measuring.** See the report for what has been run so far.
- **Nigerian-language output hasn't had human review.** Automated checks can't confirm meaning.
- **The corpus is a snapshot,** so recent announcements may be missing. Check the retrieval date on each citation.
- **Scanned documents are read by OCR** and can contain errors.
- **The evaluation set is small** and was also used for tuning, so its scores are optimistic.
- **Identity detection is pattern based** and can miss things.
- **One process only:** sessions and rate limits are in memory, and free-tier SQLite data doesn't survive restarts.
- **The number check has limits:** it can't catch a wrong statement that contains no number.

## Future improvements

- Human evaluation with fluent Hausa, Yoruba and Igbo reviewers
- Nigerian-language speech input and output for low-literacy users
- Automatic monitoring of INEC's site for changes, with a review step
- Pidgin and more languages
- A larger, held-out evaluation set, and hybrid keyword and vector search
- WhatsApp and SMS access

## Documentation

[Architecture](docs/architecture.md) · [API](docs/api.md) · [Privacy](docs/privacy.md) · [Responsible AI](docs/responsible_ai.md) · [Deployment](docs/deployment.md) · [Hackathon kit](docs/hackathon_kit.md) · [Evaluation report](evaluation/REPORT.md)
