"""Use IBM Bob (in the editor) as the AI for the demo case.

Bob runs inside the editor, not behind an API, so the questions go through
files instead of HTTP:

    python scripts/bob.py

1. Writes every question the app still needs answered to bob/questions/.
2. In Bob, ask it to answer each question file and save the JSON reply to
   bob/answers/ under the name given in the file.
3. Run this script again. Later questions depend on earlier answers (Bob can
   only compare a sighting once it has extracted it), so this takes about
   four rounds. When nothing is left, Bob's answers become the saved answers
   the app uses offline (data/mock/responses.json).

To go back to the hand-written answers: python scripts/build_mock.py
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import llm.client as lc
from app import pipeline
from app.main import seed_case

QUESTIONS = ROOT / "bob" / "questions"
ANSWERS = ROOT / "bob" / "answers"
PENDING = "no answer from Bob yet"


def name_for(task, user):
    try:
        p = json.loads(user)
        ident = p.get("observation_id") or p.get("source_ref") or "case"
    except json.JSONDecodeError:
        # a retry: the payload has the rejection message appended
        ident = re.search(r'"(?:observation_id|source_ref)": "([^"]+)"', user)
        ident = ident.group(1) if ident else "case"
    return f"{task}__{ident}__{lc.cache_key(task, user)[:6]}"


class BobClient:
    def __init__(self):
        self.recorded = {}
        self.asked = []
        self.bad = []

    def complete(self, system, user, schema, task=""):
        # the pipeline retries once after a failure; don't turn "not answered
        # yet" into a second question
        if PENDING in user:
            raise lc.LLMError(PENDING)
        name = name_for(task, user)
        ans = ANSWERS / f"{name}.json"
        if not ans.exists():
            QUESTIONS.mkdir(parents=True, exist_ok=True)
            (QUESTIONS / f"{name}.md").write_text(
                f"# Question {name}\n\n"
                f"Save your answer as: `bob/answers/{name}.json`\n\n"
                "Reply with ONLY the JSON object described in the instructions. "
                "No explanation and no code fences in the saved file.\n\n"
                f"## Instructions\n\n{system}\n\n"
                f"## Input\n\n```json\n{user}\n```\n")
            self.asked.append(name)
            raise lc.LLMError(PENDING)
        try:
            out = lc.parse_json(ans.read_text())
        except lc.LLMError as e:
            self.bad.append(f"{name}.json: {e}")
            raise
        self.recorded[lc.cache_key(task, user)] = out
        return out


def main():
    for old in QUESTIONS.glob("*.md"):
        old.unlink()
    ANSWERS.mkdir(parents=True, exist_ok=True)

    client = BobClient()
    lc._client = client
    case = pipeline.ingest(seed_case("bob"))
    # the narrative needs every sighting scored, and the documents need the
    # leads, so each later stage waits until the earlier one is fully answered
    if not client.asked:
        pipeline.summarise(case)
    if not client.asked:
        pipeline.documents(case)

    for b in client.bad:
        print("Could not read answer:", b)
    if client.asked:
        print(f"{len(client.asked)} question(s) for Bob in bob/questions/.")
        print("Ask Bob to answer each file and save the reply where the file says,")
        print("then run this script again.")
        return

    failed = [o.id for o in case.observations if o.extraction_failed]
    out = {lc.cache_key("ping", "ping"): {"reply": "pong"}}
    out.update(client.recorded)
    (ROOT / "data" / "mock" / "responses.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"Done. {len(client.recorded)} answers from Bob saved as the app's offline answers.")
    if failed:
        print("Sightings Bob's answers could not be used for:", ", ".join(failed))
    print("Conflicts:", [f"{f['alternative']} vs {', '.join(f['primary'])}" for f in case.conflicts] or "none")
    print("Leads:", [f"{l['rank']}. {l['title']} ({l['score']})" for l in case.leads])
    print("Now restart the app and press Load demo case, Analyse, Write documents.")


if __name__ == "__main__":
    main()
