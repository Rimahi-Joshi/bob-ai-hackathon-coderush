"""Rebuild data/mock/responses.json from the hand-written files in data/mock/authored/.

Runs the real pipeline over the seed case with a client that answers from the
authored files, and records each answer under the exact cache key the app will
look up. Rerun after changing the seed data or the shape of a payload.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import llm.client as lc
from app import pipeline
from app.main import seed_case

AUTH = ROOT / "data" / "mock" / "authored"
norm = json.loads((AUTH / "normalise.json").read_text())
comp = json.loads((AUTH / "compare.json").read_text())
comp.pop("_note", None)
narr = json.loads((AUTH / "narrative.json").read_text())
docs = {n: (AUTH / "docs" / f"{n}.txt").read_text() for n in ("lead_sheet", "appeal", "case_file")}


def expand(fields):
    out = {}
    for f in pipeline.SCORED_FIELDS:
        r, why = fields.get(f, ["unknown", "Not described."])
        out[f] = {"result": r, "reason": why}
    return {"fields": out}


class Authoring:
    def __init__(self):
        self.recorded = {}

    def complete(self, system, user, schema, task=""):
        p = json.loads(user)
        if task == "normalise":
            resp = norm[p["source_ref"]]
        elif task == "compare_descriptors":
            resp = expand(comp[p["observation_id"]])
            for f, v in resp["fields"].items():
                if v["result"] != "unknown" and not p["observation"][f]:
                    print(f"warning: {p['observation_id']}.{f} marked {v['result']} but field is null")
        elif task == "timeline_narrative":
            resp = narr
        elif task == "generate_documents":
            resp = docs
        else:
            raise lc.LLMError(task)
        self.recorded[lc.cache_key(task, user)] = resp
        return resp


client = Authoring()
lc._client = client
case = pipeline.documents(pipeline.summarise(pipeline.ingest(seed_case("mockbuild"))))

out = {lc.cache_key("ping", "ping"): {"reply": "pong"}}
out.update(client.recorded)
(ROOT / "data" / "mock" / "responses.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
print(f"{len(client.recorded)} responses written, {len(case.observations)} observations")
