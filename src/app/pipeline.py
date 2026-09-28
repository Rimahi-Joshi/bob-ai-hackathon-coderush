import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, ValidationError

from llm.client import LLMError, get_client

from . import places, scoring, timeline
from .models import (CCTVNote, Case, Descriptors, FamilyIntake, FieldCompare,
                     Observation, Tip)

log = logging.getLogger("pipeline")

PROMPTS = Path(__file__).resolve().parent.parent / "prompts"

# companions is extracted but not scored: it describes the situation, not the person
SCORED_FIELDS = [
    "distinguishing_marks", "clothing_upper", "clothing_lower", "footwear",
    "accessories", "hair", "height", "apparent_age", "build", "complexion",
]


def prompt(name):
    return (PROMPTS / f"{name}.txt").read_text()


class NormObs(BaseModel):
    observed_at: Optional[str] = None
    observed_until: Optional[str] = None
    location: Optional[str] = None
    descriptors: Descriptors = Descriptors()
    raw_text: str = ""
    extraction_notes: str = ""


class NormOut(BaseModel):
    observations: list[NormObs]


class CompareOut(BaseModel):
    fields: dict[str, FieldCompare]


def ask(task: str, payload: dict, out_model):
    """One LLM call, validated against out_model. Returns None on failure.

    A bad response is retried once with the validation error appended, which
    fixes most schema slips (missing key, string where a list was wanted). A
    second failure is not retried: the caller degrades instead of blocking the
    case on a model that is having a bad day.
    """
    client = get_client()
    system = prompt(task)
    user = json.dumps(payload, ensure_ascii=False, indent=1)
    err = None
    for attempt in range(2):
        u = user if err is None else f"{user}\n\nYour previous response was rejected: {err}\nReturn only JSON matching the schema."
        try:
            raw = client.complete(system, u, out_model.__name__, task=task)
            return out_model.model_validate(raw)
        except (LLMError, ValidationError) as e:
            err = str(e)[:500]
            log.warning("%s attempt %d failed: %s", task, attempt + 1, err)
    return None


def _clean_time(v, notes):
    if not v:
        return None
    try:
        return datetime.fromisoformat(v).isoformat(timespec="minutes")
    except ValueError:
        notes.append(f"unparseable time '{v}' dropped")
        return None


def _clean_place(v, notes):
    if v is None or v in places.PLACES:
        return v
    low = v.lower()
    for name, p in places.PLACES.items():
        if low == name.lower() or low in p["aliases"]:
            return name
    notes.append(f"location '{v}' not in the place list, left blank")
    return None


def normalise(source_type, source_ref, payload, fallback_text) -> list[Observation]:
    out = ask("normalise", payload, NormOut)
    if out is None or not out.observations:
        return [Observation(
            id=f"{source_ref}-1", source_type=source_type, source_ref=source_ref,
            raw_text=fallback_text, extraction_failed=True,
            extraction_notes="Automatic extraction failed. Needs manual entry.",
        )]
    obs = []
    for i, o in enumerate(out.observations, 1):
        notes = [o.extraction_notes] if o.extraction_notes else []
        obs.append(Observation(
            id=f"{source_ref}-{i}",
            source_type=source_type,
            source_ref=source_ref,
            observed_at=_clean_time(o.observed_at, notes),
            observed_until=_clean_time(o.observed_until, notes),
            location=_clean_place(o.location, notes),
            descriptors=o.descriptors,
            raw_text=o.raw_text or fallback_text,
            extraction_notes=" ".join(notes),
        ))
    return obs


def _context(case: Case):
    return {"subject_reported_missing_at": case.intake.reported_at}


def normalise_intake(intake: FamilyIntake) -> list[Observation]:
    payload = {
        "source_type": "family",
        "source_ref": "F01",
        "reported_at": intake.reported_at,
        "informant": f"{intake.informant_name} ({intake.relation})",
        "instruction": "Extract the last-seen event. Its descriptors are the family baseline for the missing person.",
        "known_places": places.NAMES,
        "text": intake.text,
    }
    return normalise("family", "F01", payload, intake.text)


def normalise_tip(case: Case, tip: Tip) -> list[Observation]:
    payload = {
        "source_type": "tip",
        "source_ref": tip.id,
        "received_at": tip.received_at,
        "case_context": _context(case),
        "caller": "named" if tip.caller_name else "anonymous",
        "known_places": places.NAMES,
        "text": tip.text,
    }
    return normalise("tip", tip.id, payload, tip.text)


def normalise_cctv(case: Case, note: CCTVNote) -> list[Observation]:
    payload = {
        "source_type": "cctv",
        "source_ref": note.id,
        "camera": note.camera,
        "camera_location": note.location,
        "footage_start": note.timestamp,
        "case_context": _context(case),
        "known_places": places.NAMES,
        "text": note.text,
    }
    return normalise("cctv", note.id, payload, note.text)


def compare(baseline: Descriptors, ob: Observation) -> dict[str, FieldCompare]:
    b = baseline.model_dump()
    o = ob.descriptors.model_dump()
    payload = {
        "observation_id": ob.id,
        "baseline": {f: b[f] for f in SCORED_FIELDS},
        "observation": {f: o[f] for f in SCORED_FIELDS},
    }
    out = ask("compare_descriptors", payload, CompareOut)
    result = {}
    for f in SCORED_FIELDS:
        # a field missing on either side is unknown regardless of what the
        # model said; it cannot count as evidence in either direction
        if not b[f] or not o[f]:
            result[f] = FieldCompare(result="unknown", reason="Not described." if not o[f] else "Not in family description.")
        elif out is None or f not in out.fields:
            result[f] = FieldCompare(result="unknown", reason="Comparison unavailable (model failure).")
        else:
            result[f] = out.fields[f]
    return result


def ingest(case: Case):
    """Run stages 1-2 for every raw input that has no observations yet."""
    done = {o.source_ref for o in case.observations}
    if "F01" not in done:
        case.observations.extend(normalise_intake(case.intake))
    fam = next((o for o in case.observations if o.source_type == "family"), None)
    if fam and not fam.extraction_failed:
        case.baseline = fam.descriptors
        case.last_seen_at = fam.observed_at
        case.last_seen_location = fam.location
    for t in case.tips:
        if t.id not in done:
            case.observations.extend(normalise_tip(case, t))
    for c in case.cctv:
        if c.id not in done:
            case.observations.extend(normalise_cctv(case, c))
    if case.baseline:
        for o in case.observations:
            if o.source_type != "family" and not o.comparison and not o.extraction_failed:
                o.comparison = compare(case.baseline, o)
    scoring.score_case(case)
    timeline.build(case)
    return case


class Lead(BaseModel):
    title: str
    action: str
    where: str = ""
    why: str = ""
    supports: list[str]
    confirm: str = ""
    kill: str = ""


class NarrativeOut(BaseModel):
    narrative: str
    leads: list[Lead]


def summarise(case: Case):
    """Stage 4 LLM pass: narrative and leads, then rank the leads in Python.

    Leads come from the same call as the narrative (one call instead of two).
    A lead ranks by the strongest non-family sighting behind it; ties go to
    the lead whose latest sighting is most recent, i.e. the freshest trail.
    """
    obs = {o.id: o for o in case.observations}

    def brief(oid):
        o = obs[oid]
        return {"id": o.id, "time": o.observed_at or o.observed_until, "location": o.location,
                "descriptors": {k: v for k, v in o.descriptors.model_dump().items() if v},
                "descriptor_score": o.descriptor_score, "credibility": o.credibility,
                "notes": o.extraction_notes}

    payload = {
        "subject": {"name": case.intake.subject_name,
                    "last_seen": f"{case.last_seen_at} at {case.last_seen_location}",
                    "family_notes": obs["F01-1"].extraction_notes if "F01-1" in obs else ""},
        "main_trail": [brief(r["id"]) for r in case.timeline if r["branch"] == "main"],
        "forks": [{**f, "alternative": brief(f["alternative"])} for f in case.conflicts],
        "set_aside": case.set_aside,
    }
    out = ask("timeline_narrative", payload, NarrativeOut)
    if out is None:
        case.narrative = "Narrative unavailable (model failure). The timeline and scores above are unaffected."
        case.leads = []
        return case

    leads = []
    for ld in out.leads:
        # drop ids the model made up; a lead with no real support is dropped
        sup = [s for s in ld.supports if s in obs]
        scored = [obs[s] for s in sup if obs[s].source_type != "family"]
        if not scored:
            continue
        best = max(scored, key=lambda o: o.priority)
        latest = max((o.observed_at or o.observed_until or "") for o in scored)
        leads.append({**ld.model_dump(), "supports": sup, "score": best.priority,
                      "rank_basis": f"strongest supporting sighting {best.id} (priority {best.priority})",
                      "_latest": latest})
    leads.sort(key=lambda l: (l["score"], l["_latest"]), reverse=True)
    for i, l in enumerate(leads, 1):
        l["rank"] = i
        del l["_latest"]
    case.narrative = out.narrative
    case.leads = leads
    return case


class DocsOut(BaseModel):
    lead_sheet: str
    appeal: str
    case_file: str


def documents(case: Case):
    obs = {o.id: o for o in case.observations}
    fam = obs.get("F01-1")
    payload = {
        "subject": {
            "name": case.intake.subject_name,
            "description": {k: v for k, v in (case.baseline.model_dump() if case.baseline else {}).items() if v},
            "last_seen": f"{case.last_seen_at} at {case.last_seen_location}",
            "family_notes": fam.extraction_notes if fam else "",
        },
        "informant": {"name": case.intake.informant_name, "relation": case.intake.relation,
                      "phone": case.intake.phone, "reported_at": case.intake.reported_at},
        "family_statement": case.intake.text,
        "leads": case.leads,
        "forks": case.conflicts,
        "narrative": case.narrative,
    }
    out = ask("generate_documents", payload, DocsOut)
    if out is None:
        msg = "Document generation failed (model unavailable). Timeline, scores and leads on screen are unaffected."
        case.documents = {"lead_sheet": msg, "appeal": msg, "case_file": msg}
    else:
        case.documents = out.model_dump()
    return case
