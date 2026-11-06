# Hackathon kit

## Problem statement

Nigerians trying to understand electoral rules must navigate long legal documents, scattered websites and information that goes out of date. With a general election on 16 January 2027, an answer that was right last year can now cost someone their vote.

## Solution in one line

CivicBridge AI answers electoral questions from official documents in plain language, shows the source for every fact, and says when it can't verify something.

## Technical explanation

CivicBridge AI is a retrieval-augmented generation system over 17 verified INEC sources, split into 1,183 passages and embedded with `all-MiniLM-L6-v2` in ChromaDB.

What sets it apart is that its safeguards are in code. The model cites passages by number, and citations are built from stored metadata, so it can't invent a source. Any number in an answer must appear in the cited evidence, or the system abstains. Each document has a status, so a repealed rule isn't presented as current. Answers are validated in English and then translated, and a translation is only shown if its citation markers and numbers survive. Otherwise, the user gets the English answer with an explanation.

## Demo script (about 3 minutes)

Before starting: open the Render URL once to wake the service, check `/api/health`, and rehearse each step with the live model. Answers vary, so read them as they appear rather than promising exact wording.

1. **The problem (20 s).** "INEC's FAQ says the vote-buying penalty is ₦500,000. The Electoral Act 2026 says at least ₦5,000,000. Official information can be out of date, so how does a voter know?"
2. **Time-aware answer (40 s).** Ask **"How do I register to vote?"** Show that the answer reflects the portal's notice that the CVR exercise has ended.
3. **Source check (30 s).** Ask **"How can I replace a lost PVC?"** Open the source link to the Electoral Act, section 18. "Citizens say PVC. The law says voter's card. We bridge that, and you can check it yourself."
4. **Outdated information (30 s).** Open Check Electoral Information and paste **"You can apply to replace a damaged voter's card up to 7 days before polling day."** Show the result, the evidence and the limitations.
5. **Honest limits (30 s).** Ask **"Who should I vote for?"** (declined) and **"How do I renew my driver's licence?"** (not answered). Then check **"INEC will pay every voter 5,000 naira on election day"**: insufficient evidence, not "fake news".
6. **Language (20 s).** Select Hausa and ask a suggested question. Point out the "not yet human-reviewed" label and the English version button. "We tell you what we haven't verified, including about ourselves."
7. **Close (10 s).** "Trustworthy civic AI should know when not to answer."

## Evaluation results

See [evaluation/REPORT.md](../evaluation/REPORT.md). It's generated from recorded runs, so quote numbers from there, along with the model that produced them.

## Known limitations

See the [README](../README.md#limitations). Be ready to raise these yourself: judges tend to trust a project more when it states its limits.

## Deployment checklist

See [deployment.md](deployment.md#checklist).

## Before submission

- [ ] Add `GEMINI_API_KEY` and run the `answers`, `claims` and `multilingual` suites with `--label gemini`
- [ ] Rebuild the report and read every failed question
- [ ] Get at least one fluent reviewer per language to score the review sheet, or keep the labels as they are
- [ ] Refresh sources, since notices change quickly before an election
- [ ] Deploy, then run through the checklist on a real phone
