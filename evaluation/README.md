# Evaluation

Results come from real runs and are saved in `results/`. `REPORT.md` is generated from those files.

| File | Purpose | Needs an LLM? |
|---|---|---|
| `test_questions.json` | 44 questions, 12 claims and 9 multilingual questions, with expected facts read from the documents | n/a |
| `test_rag.py` | Pytest retrieval gates against the real index | No |
| `test_embedding_backends.py` | Confirms the ONNX and Sentence Transformers vectors match | No |
| `run_evaluation.py` | Measured runs: `retrieval`, `answers`, `claims`, `multilingual` | All but `retrieval` |
| `make_report.py` | Rebuilds `REPORT.md` | No |
| `ui_check.cjs` | Browser checks: mobile, axe accessibility, keyboard, error states | No |
| `ask.py` | Ask the real pipeline one question from a terminal | Yes |

```bash
cd backend && .venv/bin/python -m pytest tests ../evaluation -q
cd .. && backend/.venv/bin/python evaluation/run_evaluation.py retrieval
backend/.venv/bin/python evaluation/run_evaluation.py answers --label gemini
backend/.venv/bin/python evaluation/run_evaluation.py claims --label gemini
backend/.venv/bin/python evaluation/run_evaluation.py multilingual --label gemini
backend/.venv/bin/python evaluation/make_report.py
```

## How to read the scores

- **The dataset is small and also tuned the system.** The threshold and query expansion were chosen using these questions, so the scores are optimistic. A held-out set would be stronger evidence.
- **Faithfulness is a proxy.** It measures the similarity of each sentence to its cited passage. It can miss a subtle error, so a sample of answers should be read by a person.
- **"Expected facts" is a keyword check.** It can pass a badly worded answer or fail a correct answer phrased differently. Read failures before trusting the number.
- **Precision is capped by design.** Time-critical notices are added to relevant questions, and related passages from other documents are often useful but don't count.
- **Multilingual meaning needs people.** Automated checks only confirm that markers and numbers survived and the text looks like the language. They can't confirm the meaning. `results/multilingual_review*.csv` is the sheet for fluent reviewers.

## Choosing the similarity threshold

`run_evaluation.py retrieval` prints a sweep over thresholds. All answerable questions were kept up to 0.50, so 0.45 was chosen to leave margin for translated queries. Two out-of-scope questions (passport, and a commissioner's phone number) score about 0.58 because they sound electoral or official, so the threshold can't stop them alone. The LLM's own abstention must handle these.
