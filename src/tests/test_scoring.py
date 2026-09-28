"""Hand-computed scoring checks. Run: python tests/test_scoring.py

Each expected number below was worked out on paper from the SCORING table
before the code was run; see the comments for the arithmetic.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("LLM_MODE", "mock")

# check the pipeline against the fixed reference answers, not answers saved by
# a live Bob or watsonx run
import tempfile
from pathlib import Path as _P
import llm.client as _lc
_lc.CACHE_PATH = _P(tempfile.mkdtemp()) / "llm_cache.json"

from app import pipeline
from app.main import seed_case
from app.models import FieldCompare
from app.scoring import score_descriptors


def cmp(**kw):
    return {f: FieldCompare(result=kw.get(f, "unknown")) for f in pipeline.SCORED_FIELDS}


# Case 1, T09 (Nehru Bridge, "17-18, tall, big"): right clothes, wrong person-shape.
# match: clothing_upper 15 + clothing_lower 10 = 25
# mismatch: height 8 + apparent_age 7 + build 6 = 21
# 25 / 46 = 54.35 -> 54.3, five known fields so no cap
s, ins, n = score_descriptors(cmp(clothing_upper="match", clothing_lower="match",
                                   height="mismatch", apparent_age="mismatch", build="mismatch"))
assert (s, ins, n) == (54.3, False, 5), (s, ins, n)

# Case 2, T04 (anonymous, railway): only two usable fields, both match.
# 22 / 22 = 100, but 2 known < 3 so capped at 50 and flagged insufficient
s, ins, n = score_descriptors(cmp(clothing_upper="match", apparent_age="match"))
assert (s, ins, n) == (50, True, 2), (s, ins, n)

# Case 3, no fields known at all (T03 "saw a boy near the market"): 0, insufficient
s, ins, n = score_descriptors(cmp())
assert (s, ins, n) == (0, True, 0), (s, ins, n)
print("descriptor score: 3 hand-computed cases ok")

case = pipeline.ingest(seed_case("scoretest"))
o = {x.id: x for x in case.observations}

# T07 dhaba waiter: named 50 + phone 10 + corroborated by CCTV C02 at the
# same dhaba 15 = 75. Descriptor 100. Priority 0.6*100 + 0.4*75 = 90.0
assert o["T07-1"].credibility == 75 and o["T07-1"].priority == 90.0, o["T07-1"].score_notes

# T04 anonymous railway: base 35, no phone, nothing within 2 h nearby, and
# contradicted by the higher-credibility dhaba branch -20 = 15.
# Priority 0.6*50 + 0.4*15 = 36.0
assert o["T04-1"].credibility == 15 and o["T04-1"].priority == 36.0, o["T04-1"].score_notes

# T14 truck cleaner: named 50 + phone 10 + corroborated by T10 at Transport
# Nagar 15, reported 72 h after the sighting -10 = 65.
# Descriptor: match 15+8=23, mismatch 8+7=15 -> 23/38 = 60.5
# Priority 0.6*60.5 + 0.4*65 = 36.3 + 26 = 62.3
assert o["T14-1"].descriptor_score == 60.5 and o["T14-1"].credibility == 65, o["T14-1"].score_notes
assert o["T14-1"].priority == 62.3, o["T14-1"].priority
print("credibility and priority: 3 hand-computed seed cases ok")
