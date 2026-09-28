# Solution overview

**TRACE** is a correlation
layer for missing-person cases. Free-text reports from three sources go in; a
reconciled timeline, ranked investigative leads and three ready-to-use
documents come out.

## The core mechanism

```
raw text  ->  sightings  ->  compared with the family's description
          ->  scored  ->  timeline with conflicts flagged  ->  leads  ->  documents
```

1. **Read (AI).** Each report becomes one or more *sightings*: when, where,
   and what the person looked like (11 details). Anything not said stays
   blank; hedges like "I think" are kept as notes.
2. **Compare (AI).** Each sighting is compared with the family's description,
   detail by detail: *match*, *mismatch* or *unknown*. The AI only judges
   wording ("dark blue hoodie" vs "navy sweatshirt").
3. **Score (plain Python, no AI).**
   - *Description match*: weighted by how identifying each detail is (a scar
     counts 25, complexion 5). Details nobody mentioned don't count either way.
   - *Credibility*: source type, a contact number, independent corroboration,
     contradiction with a more trusted sighting, late reporting.
   - *Priority* = 0.6 × match + 0.4 × credibility.
4. **Timeline and conflicts (plain Python).** Sightings are placed in order.
   Two sightings **conflict** if the travel time between the places is longer
   than the time between them. The more trusted side stays on the trail and
   the other is kept as **"Unreconciled — requires field verification"**.
   Nothing is silently dropped.
5. **Leads and documents (AI, checked by Python).** The AI proposes leads
   that must cite real sighting IDs; Python ranks them by the strongest
   supporting evidence and drops any lead citing evidence that doesn't exist.
   The AI then writes three documents from the same facts: an investigative
   lead sheet, a public appeal (family-confirmed details only), and a case
   file draft where every unknown field reads "Pending — not stated by
   informant".

## What makes it different

- **The AI never produces a number.** Scores, rankings and conflict
  decisions are deterministic code, with every constant in one table
  (`src/app/scoring.py`) that the UI shows on screen. "How did you get that
  score?" always has an answer.
- **Contradictions are surfaced, not resolved.** Most tools would pick the
  likelier sighting. We show both, because the weaker one might be right.
- **No fabrication by design.** Prompts forbid it, and code enforces it: a
  detail blank on either side is forced to "unknown", unknown places become
  blank, lead citations are verified, and a bad AI answer degrades to "needs
  manual entry" instead of crashing.
- **Works offline.** Every AI answer is cached to disk, so a demo or a
  field deployment doesn't depend on connectivity.

## Where IBM Bob fits

IBM Bob is the AI behind every language step. With `LLM_MODE=bob`, the
`BobClient` in `src/llm/client.py` sends each prompt (instructions + exact
input) to Bob through Bob Shell (`bob run`, authenticated with a Bob API
key) and validates Bob's JSON answer like any other. Each call runs in an
empty scratch folder with a single turn and a cost cap, so Bob answers the
question and nothing else. Answers are cached, so a demo can be replayed
offline on Bob's own output. The same prompts also drive IBM watsonx.ai
through the live adapter.

The reference answers shipped in `src/data/mock/` let the demo run out of
the box; a Bob run replaces them.

## Key design decisions

| Decision | Why |
|---|---|
| Scores in Python, not the AI | Defensible, testable, identical every run |
| Unknown details excluded from the score | Absence of information is not evidence |
| Fixed list of 12 places with a travel-time matrix | Conflict detection without maps or geocoding; works offline |
| JSON files, no database | One case at a time; zero setup |
| One prompt file per AI task (`src/prompts/`) | Editable without touching code |
| Cache every AI answer | Instant, repeatable demo; immune to network failure |

## The user experience

1. **Home:** click *Load demo case* (or fill in *New case* with the
   family's details).
2. **Reports:** every report received, each expandable to what was said.
3. Click *Analyse reports*: the **Timeline** shows a short summary, a red
   *Two reports disagree* panel, and every sighting with a one-word result
   (Strong match / Possible / Needs checking / Not used). Click a sighting
   to see which details matched and the score as a plain sum.
4. **Leads:** what to do, where, why, which reports back it, and what would
   confirm or rule it out.
5. Click *Write documents*: the three documents, each downloadable as `.txt`.
