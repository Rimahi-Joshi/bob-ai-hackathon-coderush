# Problem statement

**IBM x NFSU hackathon, Track 3 (Social Impact), problem statement 07:
Missing Person Investigation Assistant.**

## The problem

India records **80,000+ missing children every year** (NCRB 2022). The first
24 hours of a search matter most, and they are spent on paperwork and on
information that nobody puts side by side.

During those hours information arrives from three directions at once:

- **The family** describes the person: clothes, a scar, a school bag, habits,
  where they might go. The description is given verbally, often more than
  once, to different people.
- **The public** phone in tips once a poster circulates. Some are precise,
  many are vague, some contradict each other, some describe a different
  person entirely. They are noted down as they come.
- **CCTV operators** review footage and describe what they see in their own
  terse words.

Each source is handled separately. There is no **correlation layer**: nothing
that checks each tip against the family's description, lines the sightings up
in time and place, notices that two tips cannot both be true, and turns the
result into a clear next action for the investigating officer.

## Who experiences it

- **Investigating officers (IOs)**, who must decide within hours which tips
  to follow up, with limited people and vehicles.
- **Control-room and helpline staff**, who receive tips with no quick way to
  judge them.
- **Families**, who repeat the same description to several people and wait
  for the paperwork (missing-person entry, public appeal) to be done.

## Why existing approaches fall short

- Missing-person portals and registers record the case and match it against
  found persons later. They don't help triage a live stream of unverified
  tips during an active search.
- Tips kept in notebooks or spreadsheets can't be compared against a
  description consistently. Two officers will weigh the same tip differently.
- A generic AI chatbot can summarise text, but it will also **fill gaps with
  plausible guesses** and quietly resolve contradictions. In an investigation
  a confident wrong detail can send a search the wrong way, and a dropped
  contradiction can hide the real lead.

## What a solution must do

1. Turn messy free text (family statement, helpline tips, CCTV notes) into
   structured sightings **without inventing anything**.
2. Judge each sighting against the family's description in a way that can be
   **explained and defended**, not a black-box score.
3. Build a timeline and **flag sightings that cannot both be true** instead of
   silently choosing one.
4. Produce what the police need next: a ranked lead sheet, a public appeal,
   and a pre-filled case file that marks missing information as pending.

## Why now

Tip volume rises sharply once an appeal goes out on WhatsApp and social
media, exactly when investigators have the least time. AI models are now good
enough at reading messy, multilingual-flavoured text to do the first pass, if
they are constrained so that every number and every decision stays
traceable to the evidence.
