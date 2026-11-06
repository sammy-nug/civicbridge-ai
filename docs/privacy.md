# Privacy

CivicBridge AI is designed to work without knowing who you are.

## What we never ask for

PVC numbers, Voter Identification Numbers, NINs, passwords, names or addresses. There are no accounts.

## If someone types identity details anyway

Before anything else happens, the backend removes patterns that look like VINs, labelled ID numbers, long numbers, Nigerian phone numbers, email addresses and passwords. The removed text reaches neither the AI provider nor storage, and the user is told it was removed.

**This is pattern matching, so it can miss things**, such as a name or an unusually formatted number. Users are told not to enter such details.

## What is stored

| Data | Where | How long |
|---|---|---|
| Response record: random id, type, language, outcome, speed, time | SQLite | Until deleted |
| Feedback: rating and optional comment, with identity details removed | SQLite | Until deleted |
| Recent question and answer turns, in English, for follow-ups | Server memory only | Up to 30 minutes, lost on restart |
| Rate-limit counters by IP address | Server memory only | About a minute, and until the next day for the daily limit |
| Today's answers to first questions, with the question text, to save AI requests. Skipped when identity details were removed | Server memory only | Replaced after 500 answers, unused after the day ends, lost on restart |
| Language and data saver preference | The user's browser | Until cleared |

Question text, answers and IP addresses are not written to the database, and tests check that questions don't reach it. Neither the app nor its responses set advertising or tracking cookies.

## Third parties

To answer, the question (after identity details are removed) and the retrieved passages are sent to the configured AI provider, and **its data policy then applies.**

On the Gemini API's unpaid quota, [Google's terms](https://ai.google.dev/gemini-api/terms) say submitted content and responses may be used to improve its products, and that human reviewers may read them. Google advises against submitting sensitive or personal information. On paid usage, the terms say prompts and responses aren't used to improve products. A public launch should use paid usage or a self-hosted model.

The hosting providers (Vercel and Render) may keep their own server logs, including IP addresses.

## Before a public launch

The above describes the code, not a legal review. A public launch should have a review against the Nigeria Data Protection Act 2023, a retention period for feedback, and a contact for privacy requests.
