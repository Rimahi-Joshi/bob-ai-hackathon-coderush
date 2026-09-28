from typing import Literal, Optional

from pydantic import BaseModel, Field

SourceType = Literal["family", "tip", "cctv"]
FieldResult = Literal["match", "mismatch", "unknown"]

DESCRIPTOR_FIELDS = [
    "height", "build", "complexion", "clothing_upper", "clothing_lower",
    "footwear", "hair", "distinguishing_marks", "accessories",
    "apparent_age", "companions",
]


class FamilyIntake(BaseModel):
    informant_name: str
    relation: str
    phone: Optional[str] = None
    subject_name: str
    reported_at: str
    text: str


class Tip(BaseModel):
    id: str = ""
    caller_name: Optional[str] = None  # None means anonymous
    phone: Optional[str] = None
    received_at: str
    text: str


class CCTVNote(BaseModel):
    id: str = ""
    camera: str
    location: str
    timestamp: str
    operator: Optional[str] = None
    text: str


class Descriptors(BaseModel):
    height: Optional[str] = None
    build: Optional[str] = None
    complexion: Optional[str] = None
    clothing_upper: Optional[str] = None
    clothing_lower: Optional[str] = None
    footwear: Optional[str] = None
    hair: Optional[str] = None
    distinguishing_marks: Optional[str] = None
    accessories: Optional[str] = None
    apparent_age: Optional[str] = None
    companions: Optional[str] = None


class FieldCompare(BaseModel):
    result: FieldResult
    reason: str = ""


class Observation(BaseModel):
    id: str
    source_type: SourceType
    source_ref: str
    observed_at: Optional[str] = None
    # observed_at can be a range; the end goes here, null for a point in time
    observed_until: Optional[str] = None
    location: Optional[str] = None
    descriptors: Descriptors = Field(default_factory=Descriptors)
    raw_text: str = ""
    extraction_notes: str = ""
    extraction_failed: bool = False

    comparison: dict[str, FieldCompare] = Field(default_factory=dict)
    descriptor_score: Optional[float] = None
    insufficient: bool = False
    credibility: Optional[float] = None
    priority: Optional[float] = None
    score_notes: list[str] = Field(default_factory=list)


class Case(BaseModel):
    id: str
    created_at: str
    intake: FamilyIntake
    tips: list[Tip] = Field(default_factory=list)
    cctv: list[CCTVNote] = Field(default_factory=list)
    baseline: Optional[Descriptors] = None
    last_seen_at: Optional[str] = None
    last_seen_location: Optional[str] = None
    observations: list[Observation] = Field(default_factory=list)
    timeline: list[dict] = Field(default_factory=list)
    conflicts: list[dict] = Field(default_factory=list)
    set_aside: list[dict] = Field(default_factory=list)
    leads: list[dict] = Field(default_factory=list)
    narrative: str = ""
    documents: dict[str, str] = Field(default_factory=dict)
