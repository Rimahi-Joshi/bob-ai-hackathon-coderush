# The demo dataset (`src/data/seed/`)

What the AI works on, how everything is identified, how the scores are
calculated, and the rules the AI must follow. Numbers in this file come from
the current code (`src/app/scoring.py`) and are checked in `src/tests/test_scoring.py`.

**Replacing the dataset:** put a new case in `src/data/seed/case.json` (same shape)
and, if the town changes, new places in `src/data/seed/places.json`. The saved AI
answers only cover the current case, so regenerate them afterwards (with IBM Bob
via `scripts/bob.py`, or live watsonx.ai).

**A second case** is included for testing with a live AI:
`src/data/seed/case_2.json` (Kavya Solanki, 13, missing from Ambika Society,
trail north-east to the railway station; conflict: named railway-platform
vendor T08 vs anonymous highway-dhaba tip T04, 90 min apart; C02 platform
camera backs the named caller). It follows the same design rules as below.
Open it with `SEED_CASE=case_2` in `src/.env`; it has no saved answers, so it
needs `LLM_MODE=bob` or `live`.

---

## 1. The case

One made-up case set in a fictional town, **Devgadh**, on the NH-48 highway.
All names, phone numbers and places are invented; phone numbers use the dummy
range `90000 000xx`.

**Missing person:** Aarav Rathod, 14. Reported by his mother, Meena Rathod,
on 19 Sep 2026 at 18:40. Last seen leaving home in **Shanti Nagar Colony at
about 07:15**, saying he was going to school.

**Inputs: 18 free-text reports**

| Kind | Count | Style |
|---|---|---|
| Family report | 1 | The mother's statement: long, emotional, disorganised |
| Phone tips | 14 | Helpline voice: hedging ("I think", "maybe"), irrelevant detail, Indian English |
| CCTV notes | 3 | Terse operator shorthand ("M juv, est 13-15 yrs, thin build") |

**Places:** exactly 12 fixed places (home, school, market, bus stand, railway
station, Lake Garden, Nehru Bridge, industrial estate, Transport Nagar truck
yard, highway dhaba, toll plaza, Ambika Society). Road travel times come from
18 hand-written road links in `data/seed/places.json`.

---

## 2. How things are identified

| ID | What it is | Example |
|---|---|---|
| `F01` | The family report (only one) | Mother's statement |
| `T01`–`T14` | Phone tips, in the order received | `T07` = the dhaba waiter's call |
| `C01`–`C03` | CCTV notes | `C02` = pump camera beside the dhaba |
| `T07-1` | **A sighting**: report ID + sighting number | The 1st sighting in tip T07 |
| `K1` | A conflict (fork) between sightings | Dhaba vs railway clash |
| Lead 1, 2, 3 | Leads, numbered by rank | Lead 1 = trace the orange truck |

**Why "-1"?** One report can describe several sightings ("at the market at 8,
then the bus stand at 9"). The AI splits them into `T05-1`, `T05-2` and so on.
Every report in the demo has one sighting, so all IDs end in `-1`.

`F01-1` is special: it is the family's last-seen record, and its description
is the **baseline** that every other sighting is compared against.

---

## 3. The descriptors (what the person looked like)

Each sighting records 11 details. Any of them can be blank:

> height, build, complexion, top (`clothing_upper`), trousers
> (`clothing_lower`), footwear, hair, distinguishing marks, bag / items
> (`accessories`), apparent age, companions

**Baseline, from the family report (`F01-1`):**

| Detail | Value |
|---|---|
| Height | About 5 ft 2 in |
| Build | Thin |
| Complexion | Wheatish |
| Hair | Short, slightly curly, side parting |
| Distinguishing marks | **Scar about 2 cm above the left eyebrow** |
| Top | Navy blue hoodie with "NY" printed in white |
| Trousers | Grey track pants with two white side stripes |
| Footwear | Blue Bata floaters |
| Bag / items | Maroon Skybags backpack, knotted left strap, Spider-Man keychain; blue asthma inhaler |
| Age | 14 |
| Companions | Alone |

For every other sighting, the AI compares 10 details with the baseline and
labels each one **match**, **mismatch** or **unknown**. (Companions are
recorded but not scored.)

---

## 4. Description match score (0–100)

Plain arithmetic in Python, not the AI.

| Detail | Points | Why |
|---|---|---|
| Distinguishing marks | 25 | Scars and birthmarks are near-unique |
| Top | 15 | Specific, but can be changed |
| Trousers | 10 | Same |
| Footwear | 8 | Often overlooked, rarely changed |
| Bag / items | 8 | |
| Hair | 8 | |
| Height | 8 | |
| Age | 7 | |
| Build | 6 | |
| Complexion | 5 | Subjective; described inconsistently |

**Score = points that match ÷ points mentioned × 100**

- Details nobody mentioned are left out completely. Not knowing is not
  evidence either way.
- **Fewer than 3 details mentioned:** the score is capped at 50 and marked
  **"insufficient detail"**.

**Worked example, T09-1** ("tall, 17-18, blue hoodie, grey pants"):
- Match: top 15 + trousers 10 = 25
- Mismatch: height 8 + age 7 + build 6 = 21
- 25 ÷ 46 × 100 = **54.3**

---

## 5. Credibility score (0–100)

Also plain arithmetic.

| Rule | Points |
|---|---|
| Starting point | family **90** · CCTV **80** · named caller **50** · anonymous caller **35** |
| Caller left a phone number | **+10** |
| **Corroborated:** another believable sighting within 2 hours at the same or a neighbouring place | **+15** (counted once) |
| **Contradicted:** physically impossible alongside a more trusted sighting (travel time longer than the gap between them) | **−20** |
| **Stale:** reported more than 48 hours after the sighting | **−10** |

- Only sightings with a description match of **50 or more** are "believable";
  only they can corroborate or contradict. A sighting of a different boy says
  nothing about where Aarav was.
- The family record takes no part in corroboration or contradiction.

**Overall priority = 0.6 × description match + 0.4 × credibility**

On screen: **80+** strong match · **50–79** possible · **below 50** weak.

---

## 6. How the 18 reports were designed, and what they score

| Group | Sighting | Description | Credibility | Priority | Outcome |
|---|---|---|---|---|---|
| Family baseline | F01-1 (home, 07:15) | n/a | 90 | n/a | Start of trail |
| **Strong trail** (heading south) | T01-1 market 07:45 | 100 | 75 | 90 | Main trail |
| | T02-1 bus stand 08:30 | 100 | 75 | 90 | Main trail |
| | T10-1 Transport Nagar 09:30 | 100 | 75 | 90 | Main trail |
| | T12-1 toll plaza 12:30 | 100 | 75 | 90 | Main trail |
| **CCTV backing the trail** | C01-1 bus stand 08:36 | 100 | 95 | 98 | Main trail |
| | C02-1 dhaba 11:12 | 100 | 95 | 98 | Main trail |
| **Conflict, named side** | T07-1 dhaba 11:00–11:30 | 100 | 75 | 90 | Primary side of K1 |
| **Conflict, anonymous side** | T04-1 railway 11:30 | 50 (capped) | 15 | 36 | "Needs checking" side of K1 |
| **Partial** (right clothes, wrong or no age) | T06-1 Lake Garden 08:15 | 100 (only 3 details) | 75 | 90 | Main trail |
| | T09-1 Nehru Bridge 09:00 (says 17–18) | 54.3 | 75 | 62.6 | Main trail |
| | T14-1 Transport Nagar 10:00 (says 19–20, 3 days late) | 60.5 | 65 | 62.3 | Main trail |
| **Different person** | T05-1 bearded 25-year-old | 0 | 60 | 24 | Set aside |
| | T08-1 chubby 8-year-old | 0 | 60 | 24 | Set aside |
| | T11-1 fair 16-year-old | 0 | 35 | 14 | Set aside |
| **CCTV of someone else** | C03-1 railway platform | 0 | 80 | 32 | Set aside |
| **Vague** | T03-1 "a boy near the market" | 0, insufficient | 35 | 14 | Set aside (no time) |
| | T13-1 "Friday or Saturday" | 0, insufficient | 60 | 24 | Set aside (no time) |

Nothing is deleted. Set-aside reports stay visible with the reason.

### Three hand-checked examples (`tests/test_scoring.py`)

| Sighting | Credibility | Description | Priority |
|---|---|---|---|
| **T07-1** dhaba waiter | 50 named + 10 phone + 15 backed by C02-1 = **75** | 100 | 0.6 × 100 + 0.4 × 75 = **90** |
| **T04-1** anonymous railway | 35 − 20 contradicted by C02-1 = **15** | 50 (2 details, capped) | 0.6 × 50 + 0.4 × 15 = **36** |
| **T14-1** truck cleaner | 50 + 10 + 15 backed by T10-1 − 10 (72 h late) = **65** | 23 ÷ 38 = **60.5** | 0.6 × 60.5 + 0.4 × 65 = **62.3** |

---

## 7. The key moment: conflict K1

- The dhaba and the railway station are **90 minutes** apart by road.
- T04-1 (railway, 11:30) overlaps the dhaba sightings T07-1 and C02-1, and
  the toll plaza sighting T12-1 an hour later is also out of reach.
- Both can't be true. The more trusted dhaba side stays on the trail.
- T04-1 is kept, labelled **"Unreconciled — requires field verification"**,
  because the railway camera (C03) did not cover general coaches 1–3, so the
  tip cannot be ruled out.

## 8. Leads (ranked by their strongest supporting sighting)

| Rank | Lead | Score | Based on |
|---|---|---|---|
| 1 | Trace the orange-cabin RJ truck south on NH-48 | 98 | C02-1, T07-1, T12-1, T10-1 |
| 2 | Alert Surat police and the uncle's family | 90 | T10-1, T12-1, F01-1 |
| 3 | Verify the railway station branch | 36 | T04-1, C03-1 |

---

## 9. Rules the AI must follow

### What it must do
1. **Never invent anything.** If a detail wasn't said, it stays blank.
   "He looked same like the photo" goes into the notes, not the description.
2. **Keep hedges.** "I think", "maybe" and "not sure" are recorded in the notes.
3. **Places** must be one of the 12 known names, or blank.
4. **Times** in the form `2026-09-19T11:30:00`. Ranges use a start and an
   end; "before 12" sets only the end; no time given means blank.
5. **Split** a report into several sightings when it describes more than one.
6. **Cite IDs** (`T07-1`, `C02-1`) in leads and the lead sheet, and only IDs
   that exist.
7. **Never resolve a conflict.** The unreconciled side stays unreconciled.
8. **Public appeal:** only the family's description; no tips, vehicles or guesses.
9. **Case file:** anything not stated is "Pending — not stated by informant".
10. **Answer in JSON** exactly matching the format in each file in `prompts/`.

### What it never does
- Compute any score, credibility, priority or lead rank.
- Decide what counts as a conflict.

All of that is plain Python, so every number can be explained.

### Safety nets in the code, whatever the AI says
- A detail blank on either side is forced to "unknown".
- An unknown place becomes blank, with a note.
- A time that can't be read is dropped, with a note.
- Lead IDs that don't exist are removed; a lead left with no support is dropped.
- A broken answer gets one retry; after a second failure the report shows
  "needs manual entry" instead of crashing.
- The smoke test checks the public appeal contains no investigation details.

---

## 10. Checklist for the live test (Bob / watsonx)

When the real AI replaces the saved answers, check:

- [ ] The strong trail (T01, T02, T10, T12, C01, C02, T07) still scores 80 or more
- [ ] Conflict **K1** still appears, with T04-1 as the "needs checking" side
- [ ] T12-1's bag stays **blank** (the vendor didn't see it)
- [ ] T07-1's hoodie colour stays **"not stated"**
- [ ] T04-1's "looked same like the photo" is in the notes, not the description
- [ ] T13-1 has **no date** (the caller wasn't sure if it was Friday or Saturday)
- [ ] The different-person tips (T05, T08, T11, C03) score low and are set aside
- [ ] Every ID in the leads exists
- [ ] The public appeal has no tip, vehicle or ID details
