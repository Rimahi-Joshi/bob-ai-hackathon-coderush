import json
from pathlib import Path

_raw = json.loads((Path(__file__).resolve().parent.parent / "data" / "seed" / "places.json").read_text())

PLACES = {p["name"]: p for p in _raw["places"]}
NAMES = list(PLACES)


def _travel_matrix():
    # TODO: travel matrix is hand-coded for the demo locations; real version needs a routing service
    inf = float("inf")
    d = {a: {b: (0 if a == b else inf) for b in NAMES} for a in NAMES}
    for a, b, mins in _raw["edges"]:
        d[a][b] = d[b][a] = mins
    for k in NAMES:
        for i in NAMES:
            for j in NAMES:
                if d[i][k] + d[k][j] < d[i][j]:
                    d[i][j] = d[i][k] + d[k][j]
    return d


TRAVEL_MINUTES = _travel_matrix()
ADJACENT = {a: {b for x, y, _ in _raw["edges"] for b in (x, y) if a in (x, y) and b != a} for a in NAMES}


def travel(a, b):
    if a is None or b is None:
        return None
    return TRAVEL_MINUTES[a][b]


def near(a, b):
    return a == b or b in ADJACENT.get(a, ())
