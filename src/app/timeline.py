from .models import Case
from .scoring import SCORING, impossible, span

UNRECONCILED = "Unreconciled — requires field verification"


def where(o):
    return f"{o.id} ({o.location}, {span(o)[0]:%H:%M})"


def build(case: Case):
    """Split observations into the main trail, forks and set-aside items.

    Most trusted first: each sighting joins the main trail unless it is
    physically impossible alongside one already there (travel time longer than
    the gap between them). Those that clash are never dropped or silently
    resolved; each becomes a fork against the sightings it clashes with.
    """
    usable, aside = [], []
    for o in case.observations:
        if o.extraction_failed:
            aside.append({"id": o.id, "why": "extraction failed, needs manual entry"})
        elif span(o) is None:
            aside.append({"id": o.id, "why": "no time given"})
        elif o.location is None:
            aside.append({"id": o.id, "why": "no recognisable place given"})
        elif o.descriptor_score < SCORING["plausible_min"]:
            aside.append({"id": o.id, "why": f"low descriptor match ({o.descriptor_score})"})
        else:
            usable.append(o)

    main, alt = [], []
    for o in sorted(usable, key=lambda o: (-o.credibility, -o.priority)):
        (alt if any(impossible(o, m) for m in main) else main).append(o)

    forks = []
    for i, a in enumerate(alt, 1):
        clash = [m for m in main if impossible(a, m)]
        forks.append({
            "id": f"K{i}",
            "label": UNRECONCILED,
            "alternative": a.id,
            "primary": [m.id for m in clash],
            "reason": f"{where(a)} cannot be reconciled with {', '.join(where(m) for m in clash)}: "
                      f"the travel time between them is longer than the time between the sightings. "
                      f"The higher-credibility branch is shown as primary.",
        })

    fork_of = {f["alternative"]: f["id"] for f in forks}
    for f in forks:
        for p in f["primary"]:
            fork_of.setdefault(p, f["id"])

    rows = [{"id": o.id, "start": span(o)[0].isoformat(timespec="minutes"),
             "location": o.location,
             "branch": "alternative" if o in alt else "main",
             "fork": fork_of.get(o.id)} for o in usable]
    rows.sort(key=lambda r: r["start"])

    case.timeline = rows
    case.conflicts = forks
    case.set_aside = aside
    return case
