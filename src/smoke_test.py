import os

os.environ.setdefault("LLM_MODE", "mock")

# check the pipeline against the fixed reference answers, not answers saved by
# a live Bob or watsonx run
import tempfile
from pathlib import Path as _P
import llm.client as _lc
_lc.CACHE_PATH = _P(tempfile.mkdtemp()) / "llm_cache.json"

from fastapi.testclient import TestClient

from app.main import app
from llm.client import MockClient

c = TestClient(app)

r = c.get("/api/health")
assert r.status_code == 200 and r.json()["status"] == "ok", r.text
print("health ok")

assert MockClient().complete("", "ping", "ping", task="ping") == {"reply": "pong"}
print("mock client ok")

assert c.get("/").status_code == 200
print("index ok")

r = c.get("/api/case/demo/seed")
assert r.status_code == 200, r.text
case = r.json()
assert len(case["tips"]) == 14 and len(case["cctv"]) == 3
assert c.get("/api/case/demo").json()["intake"]["subject_name"] == "Aarav Rathod"
print("seed ok")

from app.places import TRAVEL_MINUTES
assert TRAVEL_MINUTES["Sher-e-Punjab Dhaba, NH-48"]["Railway Station"] == 90
assert all(TRAVEL_MINUTES[a][b] == TRAVEL_MINUTES[b][a] for a in TRAVEL_MINUTES for b in TRAVEL_MINUTES)
print("travel matrix ok")

case = c.post("/api/case/demo/analyse").json()
obs = {o["id"]: o for o in case["observations"]}
assert len(obs) == 18 and not any(o["extraction_failed"] for o in obs.values())
assert case["baseline"]["distinguishing_marks"]
assert obs["T12-1"]["descriptors"]["accessories"] is None  # bag not seen: must stay null
print("stage 1-2 on seed ok")

forks = case["conflicts"]
assert len(forks) == 1 and forks[0]["alternative"] == "T04-1", forks
assert forks[0]["label"] == "Unreconciled — requires field verification"
assert "C02-1" in forks[0]["primary"]
alt = [r for r in case["timeline"] if r["branch"] == "alternative"]
assert [r["id"] for r in alt] == ["T04-1"]
print("fork ok:", forks[0]["reason"][:70], "...")

leads = case["leads"]
assert leads and leads[0]["rank"] == 1 and "C02-1" in leads[0]["supports"], leads
assert leads[-1]["title"].startswith("Verify the railway")
docs = c.post("/api/case/demo/documents").json()["documents"]
assert set(docs) == {"lead_sheet", "appeal", "case_file"}
assert "C02-1" in docs["lead_sheet"] and "[CONTROL ROOM NUMBER]" in docs["appeal"]
assert "T07" not in docs["appeal"] and "RJ" not in docs["appeal"]  # no investigative detail in public notice
assert "Pending fields:" in docs["case_file"]
print("documents ok")
print("leads ok:", [(l["rank"], l["score"], l["title"][:30]) for l in leads])

r = c.post("/api/case/demo/tip", json={"caller_name": None, "received_at": "", "text": "saw him at the temple"})
assert r.status_code == 200
new = [o for o in r.json()["observations"] if o["source_ref"] == "T15"]
assert new and new[0]["extraction_failed"], new
print("unknown input degrades to manual entry ok")
