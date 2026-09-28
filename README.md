# TRACE: Missing Person Investigation Assistant

A correlation layer for the first 24 hours of a missing-person search.
Family statements, helpline tips and CCTV notes go in as free text; a
reconciled timeline, ranked investigative leads and three ready-to-use
documents come out, with every score explainable and every contradiction
flagged rather than hidden.

## Team

| | |
|---|---|
| Team name | [TEAM NAME] |
| Track | AI (IBM x NFSU problem statement 07, Track 3: Social Impact) |
| Lead | [LEAD NAME], [LEAD EMAIL] |
| Members | [MEMBER NAME], [MEMBER NAME] |

## Problem statement

India records 80,000+ missing children a year (NCRB 2022), and the first 24
hours are spent on paperwork while tips, CCTV notes and the family's
description sit in separate places. Nobody checks each tip against the
description, lines the sightings up in time and place, or notices when two
tips cannot both be true. More in [docs/problem-statement.md](docs/problem-statement.md).

## Solution

AI reads the messy text into structured sightings and compares each one
with the family's description, detail by detail. Plain Python then scores
every sighting, builds the timeline, and flags any two sightings that are
physically impossible together (the travel time is longer than the time
between them) as **"Unreconciled — requires field verification"**. The AI
proposes leads that must cite real evidence, and writes a lead sheet, a
public appeal and a case file. More in [docs/solution-overview.md](docs/solution-overview.md).

## Key features

- **Structured extraction without fabrication:** unknown details stay blank;
  hedges ("I think") are kept as notes; code forces "unknown" when a detail
  is missing on either side.
- **Explainable scoring:** description match weighted by identifying power
  (scar 25, complexion 5), credibility from source, contact number,
  corroboration, contradiction and late reporting. All constants live in one
  table that the app shows on screen.
- **Conflict detection:** sightings that can't both be true are shown side by
  side, the more trusted one on the trail, the other kept for field
  checking. Nothing is silently dropped.
- **Ranked, evidence-cited leads:** each lead cites sighting IDs (e.g.
  `C02-1`, `T07-1`); leads citing evidence that doesn't exist are removed.
- **Three documents from one set of facts:** investigative lead sheet,
  public appeal (family-confirmed details only), case file draft with every
  unknown field marked "Pending — not stated by informant".
- **Offline-first:** every AI answer is cached, so the demo runs without
  internet.

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, FastAPI, Uvicorn, Pydantic, httpx |
| Frontend | HTML, CSS, plain JavaScript (no framework, no CDN) |
| Storage | JSON files (no database) |
| IBM technology | **IBM Bob**: `LLM_MODE=bob` runs every AI step through Bob Shell (`bob run`) with an API key (`BobClient` in `src/llm/client.py`); a file-based alternative is in `src/scripts/bob.py`. **IBM watsonx.ai**: live adapter in the same file (Granite model by default) |

Architecture diagram and component table: [docs/architecture.md](docs/architecture.md).

## How to run

Full guide with troubleshooting: [docs/setup-guide.md](docs/setup-guide.md).

```bash
cd src
```
```bash
python3 -m venv .venv
```
```bash
.venv/bin/pip install -r requirements.txt
```
```bash
.venv/bin/python -m app
```

Open **http://127.0.0.1:8000**. On the Home tab click **1. Load demo case**,
**2. Analyse reports**, **3. Write documents**.

Checks (inside `src/`):

```bash
.venv/bin/python smoke_test.py
```
```bash
.venv/bin/python tests/test_scoring.py
```

## Demo

- Video: see [demo/demo-video-link.txt](demo/demo-video-link.txt)
- Live demo: not deployed (runs locally; see [demo/live-demo-url.txt](demo/live-demo-url.txt))
- Screenshots: [demo/screenshots/](demo/screenshots/)
- Demo dataset (18 reports, IDs, scores): [docs/dataset.md](docs/dataset.md)

## Known limitations

- **Saved AI answers:** the answers shipped for the demo case are reference
  answers written by the team to the same rules as the prompts, so the demo
  runs offline out of the box. Running with `LLM_MODE=bob` replaces them with
  IBM Bob's own answers.
- **Live watsonx.ai adapter not yet tested** against a real account.
- **New cases in offline mode:** a case or tip typed in that isn't the demo
  case shows "Needs manual entry" until an AI is connected.
- **Hand-coded geography:** 12 fixed places with hand-written travel times; a
  real deployment needs a routing service.
- **Prototype scope:** one case at a time, no login, no database, runs on
  localhost only, not deployed. All demo data is fictional.

## What we're most proud of

- **Contradictions are surfaced, not resolved.** The red "Two reports
  disagree" panel keeps the weaker sighting visible, because it might be
  the right one (`src/app/timeline.py`).
- **The AI never produces a number.** Every score can be explained line by
  line, and six of them are checked against hand calculations
  (`src/app/scoring.py`, `src/tests/test_scoring.py`).
- **No-fabrication guards in code**, not just in the prompt
  (`src/app/pipeline.py`).
