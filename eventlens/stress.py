"""Execution gates and auditable snapshots, separate from sentiment direction."""

import json
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import Field, field_validator

from eventlens.errors import DomainError
from eventlens.finance import (
    CENT,
    ZERO,
    Frozen,
    Money,
    Portfolio,
    PositionResult,
    Scenario,
    calculate,
    load_assets,
    match_exposure,
    scaled_shocks,
    snapshot_hash,
)
from eventlens.schemas import Eligibility, EventDetail, Record, RiskSignal, SourceRecord, digest

CALCULATION_VERSION = "linear-duration-v1"


class StressRequest(Record):
    event_id: str = Field(min_length=1, max_length=64)
    scenario_id: str = Field(min_length=1, max_length=64)
    idempotency_key: str = Field(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    override_reason: str = Field(min_length=8, max_length=1000)
    impact_score: int | None = Field(default=None, ge=1, le=10, strict=True)

    @field_validator("override_reason")
    @classmethod
    def meaningful_reason(cls, value):
        if len(value.strip()) < 8 or "\x00" in value:
            raise ValueError("An explicit meaningful comparison reason is required")
        return value.strip()


class StressRun(Frozen):
    id: str
    status: Literal["completed"] = "completed"
    event_id: str
    signal_id: str
    portfolio_version: str
    portfolio_hash: str
    scenario_id: str
    scenario_version: str
    scenario_hash: str
    calculation_version: str = CALCULATION_VERSION
    mode: Literal["automatic_live", "automatic_simulation", "manual_comparison"]
    impact_score: int
    actual_rate_shock_bp: Decimal
    actual_spread_shock_bp: Decimal
    override_reason: str | None = None
    simulation_clock: datetime | None = None
    created_at: datetime
    portfolio_snapshot: Portfolio
    scenario_snapshot: Scenario
    signal_snapshot: RiskSignal
    source_snapshot: tuple[SourceRecord, ...]
    eligibility_snapshot: Eligibility
    position_results: tuple[PositionResult, ...]
    base_total_usd: Money
    stressed_total_usd: Money
    total_pnl_usd: Money


class RunPage(Record):
    items: list[StressRun]
    total: int
    limit: int
    offset: int


class StressEngine:
    def __init__(self, store, settings, clock):
        self.store, self.settings, self.clock = store, settings, clock
        self.portfolio, self.scenarios = load_assets(settings.asset_directory)
        store.save_snapshot("portfolio", self.portfolio.version, self.portfolio.snapshot_json())
        for scenario in self.scenarios:
            store.save_snapshot(
                "scenario", scenario.id + ":" + scenario.version, scenario.model_dump_json()
            )

    def scenario(self, scenario_id):
        result = next((s for s in self.scenarios if s.id == scenario_id), None)
        if result is None:
            raise DomainError("SCENARIO_NOT_FOUND", "Scenario is not supported.", 404)
        return result

    def detail(self, event_id):
        result = self.store.event_detail(event_id)
        if result is None:
            raise DomainError("EVENT_NOT_FOUND", "Event does not exist.", 404)
        result.eligibility = self.eligibility(result)
        result.event.eligibility = result.eligibility
        return result

    def eligibility(self, detail: EventDetail):
        signal = detail.event.primary_signal
        source = next(s for s in detail.evidence if s.id == signal.source_record_id)
        scenario = next(
            (s for s in self.scenarios if s.event_subtype == signal.event_subtype), None
        )
        now = self.clock()
        simulation = (
            source.provenance_mode == "synthetic"
            and source.source_family == "synthetic"
            and source.source_id in {"sample_news", "sample_social"}
            and source.canonical_uri.startswith("synthetic://")
            and signal.simulation_clock is not None
            and not source.verified_publisher
        )
        reference = signal.simulation_clock if simulation else now
        reasons = list(signal.flags) + detail.event.review_flags
        if signal.impact_score <= 7:
            reasons.append("impact_not_above_threshold")
        if not scenario:
            reasons.append("scenario_unsupported")
        if signal.assertion_status != "asserted":
            reasons.append("event_not_asserted")
        if signal.sentiment_truncated:
            reasons.append("sentiment_truncated")
        if source.language != "en":
            reasons.append("language_requires_review")
        if not simulation:
            if source.provenance_mode != "live":
                reasons.append("non_live_mode")
            if not (
                source.verified_publisher and source.source_family in {"official_release", "social"}
            ):
                reasons.append("source_not_verified")
        age = (reference - source.published_at).total_seconds()
        if age < 0:
            reasons.append("future_publication")
        elif age > self.settings.live_max_age_hours * 3600:
            reasons.append("stale_event")
        if (
            any(
                s.assertion_status == "negated" and s.event_subtype == signal.event_subtype
                for s in detail.signals
            )
            and signal.assertion_status == "asserted"
        ):
            reasons.append("cross_source_conflict")
        mapping = match_exposure(self.portfolio, scenario, signal) if scenario else {}
        rate_ids = sorted(key for key, (rate, spread) in mapping.items() if rate)
        spread_ids = sorted(key for key, (rate, spread) in mapping.items() if spread)
        if scenario and not rate_ids and not spread_ids:
            reasons.append("no_matching_exposure")
        # A supply event needs an explicit affected supply-sector match; a generic
        # geopolitical sentence is insufficient even if a USD rate shock is defined.
        if scenario and scenario.event_subtype == "supply_disruption" and not spread_ids:
            reasons.append("supply_exposure_unresolved")
        state = (
            "needs_review" if reasons else "eligible_simulation" if simulation else "eligible_live"
        )
        if signal.impact_score <= 7:
            state = "informational"
        return Eligibility(
            state=state,
            scenario_id=scenario.id if scenario else None,
            reasons=sorted(set(reasons)),
            rate_position_ids=rate_ids,
            spread_position_ids=spread_ids,
            evaluated_at=now,
            reference_clock=reference,
        )

    def automatic(self, event_id, expected_mode):
        detail = self.detail(event_id)
        required = (
            "eligible_simulation" if expected_mode == "automatic_simulation" else "eligible_live"
        )
        if detail.eligibility.state != required:
            return None
        scenario = self.scenario(detail.eligibility.scenario_id)
        signal = detail.event.primary_signal
        identity = digest(
            event_id,
            signal.id,
            self.portfolio.version,
            scenario.id,
            scenario.version,
            snapshot_hash(self.portfolio.snapshot_json()),
            snapshot_hash(scenario.model_dump_json()),
            CALCULATION_VERSION,
        )
        previous = self.store.automatic_run(identity)
        if previous:
            return previous
        run = self._calculate(detail, scenario, signal.impact_score, expected_mode)
        return self.store.save_run(run, automatic_key=identity)

    def manual(self, request: StressRequest):
        request_hash = snapshot_hash(
            json.dumps(request.model_dump(exclude={"idempotency_key"}), sort_keys=True)
        )
        previous = self.store.idempotent_run(request.idempotency_key, request_hash)
        if previous:
            return previous
        detail = self.detail(request.event_id)
        scenario = self.scenario(request.scenario_id)
        # Manual comparisons may deliberately reverse the rate direction, but may
        # not invent an affected credit issuer/sector or an unsupported event family.
        signal = detail.event.primary_signal
        same_family = scenario.event_subtype == signal.event_subtype or (
            scenario.event_subtype in {"rate_hike", "rate_cut"}
            and signal.event_subtype in {"rate_hike", "rate_cut"}
        )
        if not same_family:
            raise DomainError(
                "SCENARIO_NOT_APPLICABLE",
                "Comparison scenario does not match the event family.",
                422,
            )
        mapping = match_exposure(self.portfolio, scenario, signal)
        if not any(rate or spread for rate, spread in mapping.values()) or (
            scenario.event_subtype == "supply_disruption"
            and not any(spread for rate, spread in mapping.values())
        ):
            raise DomainError(
                "NO_MATCHING_EXPOSURE",
                "No eligible issuer, sector, or USD rate exposure was identified.",
                422,
            )
        run = self._calculate(
            detail,
            scenario,
            request.impact_score or signal.impact_score,
            "manual_comparison",
            request.override_reason,
        )
        return self.store.save_run(
            run, idempotency_key=request.idempotency_key, request_hash=request_hash
        )

    def _calculate(self, detail, scenario, impact, mode, reason=None):
        signal = detail.event.primary_signal
        rate, spread = scaled_shocks(scenario, impact)
        results = calculate(
            self.portfolio.positions, match_exposure(self.portfolio, scenario, signal), rate, spread
        )
        pnl = sum((r.total_pnl_usd for r in results), ZERO).quantize(CENT)
        stressed = sum((r.stressed_market_value_usd for r in results), ZERO).quantize(CENT)
        if self.portfolio.base_total_usd + pnl != stressed:
            raise DomainError(
                "RECONCILIATION_FAILED", "Position and portfolio totals do not reconcile.", 500
            )
        return StressRun(
            id=uuid4().hex,
            event_id=signal.event_id,
            signal_id=signal.id,
            portfolio_version=self.portfolio.version,
            portfolio_hash=snapshot_hash(self.portfolio.snapshot_json()),
            scenario_id=scenario.id,
            scenario_version=scenario.version,
            scenario_hash=snapshot_hash(scenario.model_dump_json()),
            mode=mode,
            impact_score=impact,
            actual_rate_shock_bp=rate,
            actual_spread_shock_bp=spread,
            override_reason=reason,
            simulation_clock=signal.simulation_clock,
            created_at=self.clock(),
            portfolio_snapshot=self.portfolio,
            scenario_snapshot=scenario,
            signal_snapshot=signal,
            source_snapshot=tuple(detail.evidence),
            eligibility_snapshot=detail.eligibility,
            position_results=results,
            base_total_usd=self.portfolio.base_total_usd,
            stressed_total_usd=stressed,
            total_pnl_usd=pnl,
        )
