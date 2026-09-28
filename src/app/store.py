import json
from pathlib import Path

from .models import Case

CASES = Path(__file__).resolve().parent.parent / "data" / "cases"


def save(case: Case):
    CASES.mkdir(parents=True, exist_ok=True)
    tmp = CASES / f"{case.id}.json.tmp"
    tmp.write_text(case.model_dump_json(indent=1))
    tmp.replace(CASES / f"{case.id}.json")


def load(case_id: str) -> Case | None:
    p = CASES / f"{case_id}.json"
    if not p.exists():
        return None
    return Case.model_validate(json.loads(p.read_text()))
