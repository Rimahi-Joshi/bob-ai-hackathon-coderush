import json
import logging
import os
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from llm.client import get_client

from . import pipeline, places, scoring, store
from .models import Case, CCTVNote, FamilyIntake, Tip

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"
SEED_DIR = ROOT / "data" / "seed"

app = FastAPI(title="TRACE")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.middleware("http")
async def no_cache(request, call_next):
    # browsers kept an old app.js after the UI was rebuilt; always revalidate
    resp = await call_next(request)
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/")
def index():
    # stamp asset urls with the latest file time: Safari ignored no-cache for a
    # stylesheet it had cached earlier, so a new url is the only sure refresh
    v = int(max(p.stat().st_mtime for p in STATIC.iterdir()))
    html = (STATIC / "index.html").read_text()
    html = html.replace('/static/style.css"', f'/static/style.css?v={v}"').replace('/static/app.js"', f'/static/app.js?v={v}"')
    return HTMLResponse(html)


@app.get("/api/health")
def health():
    get_client()
    return {"status": "ok", "llm_mode": os.environ.get("LLM_MODE", "mock")}


@app.get("/api/scoring")
def get_scoring():
    return scoring.SCORING


@app.get("/api/places")
def get_places():
    return {"places": list(places.PLACES.values()), "travel_minutes": places.TRAVEL_MINUTES}


def _case(case_id) -> Case:
    case = store.load(case_id)
    if case is None:
        raise HTTPException(404, f"no case {case_id}")
    return case


@app.get("/api/case/{case_id}")
def get_case(case_id: str):
    return _case(case_id)


def seed_case(case_id) -> Case:
    # SEED_CASE picks which file in data/seed/ "Load demo case" opens (default case.json)
    name = os.environ.get("SEED_CASE") or "case"
    raw = json.loads((SEED_DIR / f"{name}.json").read_text())
    return Case(
        id=case_id,
        created_at=datetime.now().isoformat(timespec="seconds"),
        intake=FamilyIntake(**raw["intake"]),
        tips=[Tip(**t) for t in raw["tips"]],
        cctv=[CCTVNote(**c) for c in raw["cctv"]],
    )


@app.get("/api/case/{case_id}/seed")
def seed(case_id: str):
    """Load the scripted demo case under case_id, replacing whatever was there.

    Only raw inputs are loaded; observations appear once the pipeline runs.
    """
    case = seed_case(case_id)
    store.save(case)
    return case


def _now():
    return datetime.now().isoformat(timespec="seconds")


@app.post("/api/case")
def create_case(intake: FamilyIntake):
    case = Case(id=datetime.now().strftime("c%Y%m%d%H%M%S"), created_at=_now(), intake=intake)
    pipeline.ingest(case)
    store.save(case)
    return case


@app.post("/api/case/{case_id}/tip")
def add_tip(case_id: str, tip: Tip):
    case = _case(case_id)
    tip.id = f"T{len(case.tips) + 1:02d}"
    tip.received_at = tip.received_at or _now()
    case.tips.append(tip)
    pipeline.ingest(case)
    store.save(case)
    return case


@app.post("/api/case/{case_id}/cctv")
def add_cctv(case_id: str, note: CCTVNote):
    case = _case(case_id)
    note.id = f"C{len(case.cctv) + 1:02d}"
    case.cctv.append(note)
    pipeline.ingest(case)
    store.save(case)
    return case


@app.post("/api/case/{case_id}/analyse")
def analyse(case_id: str):
    case = _case(case_id)
    pipeline.ingest(case)
    pipeline.summarise(case)
    store.save(case)
    return case


@app.post("/api/case/{case_id}/documents")
def make_documents(case_id: str):
    case = _case(case_id)
    if not case.timeline:
        raise HTTPException(400, "analyse the case first")
    pipeline.documents(case)
    store.save(case)
    return case
