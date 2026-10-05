import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utcnow() -> datetime:
    return datetime.now(UTC)


def digest(*parts: str) -> str:
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()[:32]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EventClass(StrEnum):
    MACRO = "Macroeconomic"
    CREDIT = "Credit Event"
    GEO = "Geopolitical"
    MA = "Merger/Acquisition"
    PRODUCT = "Product Launch"
    UNKNOWN = "Other/Unknown"


class Span(Record):
    start: int = Field(ge=0)
    end: int = Field(ge=1)
    text: str


class Impact(Record):
    magnitude_points: int = Field(ge=0, le=5)
    scope_points: int = Field(ge=0, le=4)
    rationale: str
    rubric_version: str = "severity_v1"


class Classification(Record):
    event_class: EventClass
    event_subtype: str
    assertion_status: Literal["asserted", "speculative", "negated", "unclear"]
    impact_score: int = Field(ge=1, le=10)
    impact_components: Impact
    evidence_spans: list[Span] = Field(default_factory=list)
    affected_issuers: list[str] = Field(default_factory=list)
    affected_sectors: list[str] = Field(default_factory=list)
    affected_regions: list[str] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    classification_method: str = "phrase_rules_v2"


class SourceRecord(Record):
    id: str
    source_id: str
    source_family: Literal["official_release", "social", "synthetic", "user"]
    publisher: str
    canonical_uri: str
    linked_release_url: str | None = None
    text: str = Field(min_length=1, max_length=12000)
    text_kind: Literal["headline_summary", "full_release", "post", "supplied_text"]
    published_at: datetime
    retrieved_at: datetime
    language: str = "en"
    provenance_mode: Literal["live", "replay", "synthetic", "user"]
    content_hash: str
    verified_publisher: bool = False
    input_flags: list[str] = Field(default_factory=list)
    analysis_state: Literal["received", "analyzed", "failed"] = "received"
    error_code: str | None = None

    @field_validator("text")
    @classmethod
    def meaningful_text(cls, value):
        if not value.strip() or "\x00" in value:
            raise ValueError("Text must be nonempty and contain no NUL characters")
        return value

    @field_validator("published_at", "retrieved_at")
    @classmethod
    def aware_utc(cls, value):
        if value.tzinfo is None:
            raise ValueError("Timestamps must include a timezone")
        return value.astimezone(UTC)


class Sentiment(Record):
    score: float = Field(ge=-1, le=1, allow_inf_nan=False)
    probabilities: dict[str, float]
    model_id: str
    model_revision: str
    inference_mode: str = "local_cpu"
    token_count: int
    chunks: int
    truncated: bool = False

    @model_validator(mode="after")
    def valid_probabilities(self):
        import math

        if set(self.probabilities) != {"positive", "negative", "neutral"}:
            raise ValueError("All three sentiment labels are required")
        if any(not math.isfinite(p) or not 0 <= p <= 1 for p in self.probabilities.values()):
            raise ValueError("Invalid probability")
        if not math.isclose(sum(self.probabilities.values()), 1, abs_tol=1e-5):
            raise ValueError("Probabilities must sum to one")
        if not math.isclose(
            self.score,
            self.probabilities["positive"] - self.probabilities["negative"],
            abs_tol=1e-5,
        ):
            raise ValueError("Score must be positive minus negative probability")
        return self


class RiskSignal(Classification):
    id: str
    event_id: str
    source_record_id: str
    sentiment_score: float = Field(ge=-1, le=1, allow_inf_nan=False)
    sentiment_probabilities: dict[str, float]
    sentiment_model_id: str
    model_revision: str
    inference_mode: str
    sentiment_token_count: int
    sentiment_chunks: int
    sentiment_truncated: bool
    engine_version: str
    created_at: datetime
    simulation_clock: datetime | None = None
    review_reasons: list[str]
    stress_readiness: Literal["informational", "needs_review"]


class AnalysisResult(Record):
    source: SourceRecord
    signal: RiskSignal
    duplicate: bool = False


class Eligibility(Record):
    state: Literal["informational", "needs_review", "eligible_live", "eligible_simulation"]
    scenario_id: str | None = None
    reasons: list[str]
    rate_position_ids: list[str] = Field(default_factory=list)
    spread_position_ids: list[str] = Field(default_factory=list)
    evaluated_at: datetime
    reference_clock: datetime


class EventSummary(Record):
    id: str
    canonical_event_key: str
    grouping_method: str
    source_record_ids: list[str]
    primary_signal: RiskSignal
    source_families: list[str]
    provenance_modes: list[str]
    verified_publisher_count: int
    evidence_independent: bool
    review_flags: list[str] = Field(default_factory=list)
    eligibility: Eligibility | None = None


class EventPage(Record):
    items: list[EventSummary]
    total: int
    limit: int
    offset: int


class EventDetail(Record):
    event: EventSummary
    evidence: list[SourceRecord]
    signals: list[RiskSignal]
    stress_run_ids: list[str] = Field(default_factory=list)
    eligibility: Eligibility | None = None


class Operation(Record):
    id: str
    kind: Literal["refresh", "replay"]
    status: Literal["queued", "running", "completed", "failed", "interrupted"]
    started_at: datetime
    completed_at: datetime | None = None
    result_counts: dict[str, int] = Field(default_factory=dict)
    error_code: str | None = None


class SourceHealth(Record):
    source_id: str
    last_attempt_at: datetime | None = None
    last_success_at: datetime | None = None
    next_allowed_at: datetime | None = None
    record_count: int = 0
    error_code: str | None = None
    stale: bool = True


class Health(Record):
    status: Literal["ready", "degraded"]
    model_ready: bool
    model_id: str
    model_revision: str
    model_error_code: str | None
    engine_version: str
    sources: list[SourceHealth]
    portfolio_available: bool = False


class AnalyzeRequest(Record):
    text: str = Field(min_length=1, max_length=12000)
    published_at: datetime | None = None

    @field_validator("text")
    @classmethod
    def meaningful_text(cls, value):
        return SourceRecord.meaningful_text(value)

    @field_validator("published_at")
    @classmethod
    def aware_utc(cls, value):
        return SourceRecord.aware_utc(value) if value is not None else None


class ReplayRequest(Record):
    dataset: Literal["synthetic_events"] = "synthetic_events"


class ReplayDataset(Record):
    provenance_mode: Literal["synthetic"]
    simulation_clock: datetime
    description: str
    records: list[SourceRecord] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def synthetic_only(self):
        if self.simulation_clock.tzinfo is None:
            raise ValueError("Simulation clock must be timezone-aware")
        if any(r.provenance_mode != "synthetic" or r.verified_publisher for r in self.records):
            raise ValueError("Synthetic records must not claim verified real events")
        return self


class ErrorInfo(Record):
    code: str
    message: str


class ErrorResponse(Record):
    error: ErrorInfo


class SignalExport(Record):
    items: list[AnalysisResult]
    total: int
    engine_version: str
