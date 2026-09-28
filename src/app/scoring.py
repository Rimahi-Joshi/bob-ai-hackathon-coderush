from datetime import datetime

from . import places
from .models import Case, Observation

# Everything the scores depend on lives here so it can be put on screen and
# defended line by line. No LLM output is used below except the per-field
# match/mismatch/unknown labels from stage 2.
SCORING = {
    # identifying power of each attribute; marks are near-unique, complexion
    # is subjective and described inconsistently by callers
    "weights": {
        "distinguishing_marks": 25,
        "clothing_upper": 15,
        "clothing_lower": 10,
        "footwear": 8,
        "accessories": 8,
        "hair": 8,
        "height": 8,
        "apparent_age": 7,
        "build": 6,
        "complexion": 5,
    },
    "min_known_fields": 3,
    "insufficient_cap": 50,
    "base_credibility": {"family": 90, "cctv": 80, "named_tip": 50, "anonymous_tip": 35},
    "corroborated": 15,
    "corroboration_window_min": 120,
    "contactable": 10,
    "contradicted": -20,
    "stale": -10,
    "stale_after_hours": 48,
    # an observation must reach this descriptor score before it can corroborate
    # or contradict anything; a sighting of a different boy says nothing about
    # where Aarav was
    "plausible_min": 50,
    "priority": {"descriptor": 0.6, "credibility": 0.4},
}


def score_descriptors(comparison):
    """Weighted share of known fields that match, 0-100.

    unknown fields drop out of numerator and denominator alike: a caller not
    mentioning shoes is not evidence either way. Returns (score, insufficient,
    known_count).
    """
    w = SCORING["weights"]
    hit = known = 0
    n = 0
    for f, c in comparison.items():
        if f not in w or c.result == "unknown":
            continue
        n += 1
        known += w[f]
        if c.result == "match":
            hit += w[f]
    score = 100 * hit / known if known else 0.0
    insufficient = n < SCORING["min_known_fields"]
    if insufficient:
        score = min(score, SCORING["insufficient_cap"])
    return round(score, 1), insufficient, n


def _t(s):
    return datetime.fromisoformat(s) if s else None


def span(o: Observation):
    a, b = _t(o.observed_at), _t(o.observed_until)
    if a is None and b is None:
        return None
    return (a or b, b or a)


def gap_minutes(x, y):
    """Minutes between two time spans; 0 if they overlap."""
    sx, sy = span(x), span(y)
    if sx is None or sy is None:
        return None
    g = max((sy[0] - sx[1]).total_seconds(), (sx[0] - sy[1]).total_seconds(), 0)
    return g / 60


def impossible(x, y):
    """True if one subject cannot be at both places in the time between them."""
    g = gap_minutes(x, y)
    t = places.travel(x.location, y.location)
    if g is None or t is None:
        return False
    return t > g


def _base(o, tips):
    if o.source_type != "tip":
        return SCORING["base_credibility"][o.source_type], o.source_type
    tip = tips.get(o.source_ref)
    kind = "named_tip" if tip and tip.caller_name else "anonymous_tip"
    return SCORING["base_credibility"][kind], kind.replace("_", " ")


def score_case(case: Case):
    tips = {t.id: t for t in case.tips}
    obs = [o for o in case.observations if not o.extraction_failed]

    for o in obs:
        if o.source_type == "family":
            o.descriptor_score, o.insufficient = 100.0, False
        else:
            o.descriptor_score, o.insufficient, _ = score_descriptors(o.comparison)

    # the family's last-seen record is the baseline, not a sighting, so it
    # neither corroborates nor contradicts anything
    sightings = [o for o in obs if o.source_type != "family"]
    plausible = [o for o in sightings if o.descriptor_score >= SCORING["plausible_min"]]

    pre = {}
    for o in obs:
        cred, kind = _base(o, tips)
        notes = [f"base {cred} ({kind})"]
        tip = tips.get(o.source_ref) if o.source_type == "tip" else None
        if tip and tip.phone:
            cred += SCORING["contactable"]
            notes.append(f"+{SCORING['contactable']} contactable number")
        if o in plausible:
            found = []
            for other in plausible:
                if other.source_ref == o.source_ref or other.insufficient:
                    continue
                g = gap_minutes(o, other)
                if g is not None and g <= SCORING["corroboration_window_min"] and places.near(o.location, other.location):
                    found.append((g, o.location != other.location, other))
            if found:
                # bonus applies once; cite the closest supporting sighting
                g, adj, other = min(found, key=lambda f: (f[0], f[1]))
                cred += SCORING["corroborated"]
                where = "adjacent place" if adj else "same place"
                notes.append(f"+{SCORING['corroborated']} corroborated by {other.id} ({where}, {g:.0f} min apart)")
        if tip:
            s = span(o)
            if s is not None:
                lag = (datetime.fromisoformat(tip.received_at) - s[1]).total_seconds() / 3600
                if lag > SCORING["stale_after_hours"]:
                    cred += SCORING["stale"]
                    notes.append(f"{SCORING['stale']} stale recall (reported {lag:.0f} h after sighting)")
        pre[o.id] = cred
        o.score_notes = notes

    # contradiction is judged against pre-penalty credibility so two weak
    # tips cannot drag each other down in a loop
    for o in obs:
        cred = pre[o.id]
        if o in plausible:
            rivals = [x for x in plausible if x.source_ref != o.source_ref and pre[x.id] > cred and impossible(o, x)]
            if rivals:
                top = max(rivals, key=lambda x: pre[x.id])
                cred += SCORING["contradicted"]
                o.score_notes.append(
                    f"{SCORING['contradicted']} contradicted by {top.id} (credibility {pre[top.id]}): "
                    f"{places.travel(o.location, top.location)} min travel, {gap_minutes(o, top):.0f} min apart")
        o.credibility = max(0, min(100, cred))
        p = SCORING["priority"]
        o.priority = round(p["descriptor"] * o.descriptor_score + p["credibility"] * o.credibility, 1)
    return case
