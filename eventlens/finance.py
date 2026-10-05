"""Immutable synthetic inputs and first-order, independent-base stress arithmetic."""

import csv
import hashlib
import json
from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from pathlib import Path
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, TypeAdapter, computed_field, model_validator

from eventlens.config import ROOT
from eventlens.schemas import Classification, Record

Money = Annotated[
    Decimal, Field(ge=-(10**12), le=10**12, max_digits=15, decimal_places=2, allow_inf_nan=False)
]
Sensitivity = Annotated[
    Decimal, Field(ge=-(10**7), le=10**7, max_digits=14, decimal_places=6, allow_inf_nan=False)
]
Duration = Annotated[
    Decimal, Field(ge=0, le=30, max_digits=8, decimal_places=6, allow_inf_nan=False)
]
CENT = Decimal("0.01")
ZERO = Decimal(0)


class Frozen(Record):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Position(Frozen):
    id: str = Field(min_length=1, max_length=64)
    asset_type: Literal["loan", "bond", "swap"]
    instrument_type: Literal[
        "fixed", "floating", "corporate", "government", "payer_fixed", "receiver_fixed"
    ]
    issuer: str = Field(min_length=1, max_length=100)
    sector: str = Field(min_length=1, max_length=40)
    region: Literal["US"]
    currency: Literal["USD"]
    base_market_value_usd: Money
    notional_usd: Annotated[Decimal, Field(gt=0, le=10**12, decimal_places=2, allow_inf_nan=False)]
    rate_duration: Duration
    spread_duration: Duration
    signed_rate_pnl_per_bp: Sensitivity
    portfolio_version: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def consistent_instrument(self):
        choices = {
            "loan": {"fixed", "floating"},
            "bond": {"corporate", "government"},
            "swap": {"payer_fixed", "receiver_fixed"},
        }
        if self.instrument_type not in choices[self.asset_type]:
            raise ValueError("Instrument type does not match asset type")
        if self.asset_type == "swap":
            if self.rate_duration or self.spread_duration:
                raise ValueError("Swap uses signed sensitivity, not cash durations")
            if (self.instrument_type == "payer_fixed" and self.signed_rate_pnl_per_bp <= 0) or (
                self.instrument_type == "receiver_fixed" and self.signed_rate_pnl_per_bp >= 0
            ):
                raise ValueError("Swap sensitivity has incorrect sign")
        elif self.base_market_value_usd <= 0 or self.signed_rate_pnl_per_bp:
            raise ValueError("Cash assets require positive value and zero swap sensitivity")
        if self.sector == "sovereign" or self.instrument_type == "government":
            if (
                self.asset_type != "bond"
                or self.instrument_type != "government"
                or self.sector != "sovereign"
                or self.spread_duration
            ):
                raise ValueError(
                    "Government bonds must be sovereign and have zero corporate spread duration"
                )
        return self


class Portfolio(Frozen):
    version: str
    name: str
    provenance: Literal["synthetic"]
    currency: Literal["USD"]
    assumptions: tuple[str, ...]
    positions: tuple[Position, ...] = Field(min_length=1, max_length=1000)

    @model_validator(mode="after")
    def unique_positions(self):
        if len({p.id for p in self.positions}) != len(self.positions):
            raise ValueError("Duplicate position IDs")
        if any(p.portfolio_version != self.version for p in self.positions):
            raise ValueError("Position version differs from portfolio version")
        if self.base_total_usd <= 0:
            raise ValueError("Portfolio base total must be positive")
        return self

    @computed_field
    @property
    def base_total_usd(self) -> Decimal:
        return sum((p.base_market_value_usd for p in self.positions), ZERO).quantize(CENT)

    @computed_field
    @property
    def notional_total_usd(self) -> Decimal:
        return sum((p.notional_usd for p in self.positions), ZERO).quantize(CENT)

    def snapshot_json(self):
        return self.model_dump_json(exclude_computed_fields=True)


class Scenario(Frozen):
    id: str
    version: str
    name: str
    event_subtype: Literal["rate_hike", "rate_cut", "credit_deterioration", "supply_disruption"]
    reference_impact: Literal[8]
    rate_shock_bp: Annotated[Decimal, Field(ge=-500, le=500, decimal_places=4, allow_inf_nan=False)]
    spread_shock_bp: Annotated[Decimal, Field(ge=0, le=1000, decimal_places=4, allow_inf_nan=False)]
    exposure_rule: Literal["usd_rate", "matched_credit", "usd_rate_matched_supply"]
    assumption: str

    @model_validator(mode="after")
    def direction(self):
        if self.event_subtype == "rate_hike" and not (
            self.rate_shock_bp > 0
            and self.spread_shock_bp == 0
            and self.exposure_rule == "usd_rate"
        ):
            raise ValueError("Rate hike must have positive rate-only shock")
        if self.event_subtype == "rate_cut" and not (
            self.rate_shock_bp < 0
            and self.spread_shock_bp == 0
            and self.exposure_rule == "usd_rate"
        ):
            raise ValueError("Rate cut must have negative rate-only shock")
        if self.event_subtype == "credit_deterioration" and not (
            self.rate_shock_bp == 0
            and self.spread_shock_bp > 0
            and self.exposure_rule == "matched_credit"
        ):
            raise ValueError("Credit profile must widen matched spreads only")
        if self.event_subtype == "supply_disruption" and not (
            self.rate_shock_bp > 0
            and self.spread_shock_bp > 0
            and self.exposure_rule == "usd_rate_matched_supply"
        ):
            raise ValueError("Supply profile requires adverse rate and spread shocks")
        return self


class PositionResult(Frozen):
    position_id: str
    base_market_value_usd: Money
    rate_applied: bool
    spread_applied: bool
    rate_pnl_usd: Money
    spread_pnl_usd: Money
    total_pnl_usd: Money
    stressed_market_value_usd: Money
    explanation: str


def load_assets(directory: Path = ROOT / "data") -> tuple[Portfolio, tuple[Scenario, ...]]:
    metadata = json.loads((directory / "portfolio.json").read_text(encoding="utf-8"))
    with (directory / "portfolio.csv").open(encoding="utf-8", newline="") as handle:
        positions = tuple(Position.model_validate(row) for row in csv.DictReader(handle))
    portfolio = Portfolio.model_validate(metadata | {"positions": positions})
    scenarios = TypeAdapter(tuple[Scenario, ...]).validate_json(
        (directory / "scenarios.json").read_text(encoding="utf-8")
    )
    if len({s.id for s in scenarios}) != len(scenarios) or len(
        {s.event_subtype for s in scenarios}
    ) != len(scenarios):
        raise ValueError("Duplicate scenario IDs or subtypes")
    return portfolio, scenarios


def snapshot_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def scaled_shocks(scenario: Scenario, impact: int) -> tuple[Decimal, Decimal]:
    if not isinstance(impact, int) or isinstance(impact, bool) or not 1 <= impact <= 10:
        raise ValueError("Impact must be 1..10")
    scale = min(Decimal(impact) / Decimal(8), Decimal("1.25"))
    return scenario.rate_shock_bp * scale, scenario.spread_shock_bp * scale


def match_exposure(portfolio: Portfolio, scenario: Scenario, signal: Classification):
    result = {}
    for p in portfolio.positions:
        cash_credit = p.asset_type != "swap" and p.sector != "sovereign" and p.spread_duration > 0
        rate = (
            scenario.exposure_rule in {"usd_rate", "usd_rate_matched_supply"}
            and (
                scenario.exposure_rule == "usd_rate_matched_supply"
                or "US" in signal.affected_regions
            )
            and (p.rate_duration > 0 or p.signed_rate_pnl_per_bp != 0)
        )
        # An identified issuer never broadens to every issuer in the same sector.
        entity = (
            p.issuer in signal.affected_issuers
            if signal.affected_issuers
            else p.sector in signal.affected_sectors
        )
        spread = (
            cash_credit
            and entity
            and (
                scenario.exposure_rule == "matched_credit"
                or (
                    scenario.exposure_rule == "usd_rate_matched_supply"
                    and p.sector in {"energy", "transport"}
                )
            )
        )
        result[p.id] = (rate, spread)
    return result


def calculate(
    positions, mapping, rate_bp: Decimal, spread_bp: Decimal
) -> tuple[PositionResult, ...]:
    results = []
    if not rate_bp.is_finite() or not spread_bp.is_finite():
        raise ValueError("Shocks must be finite")
    with localcontext() as context:
        context.prec = 40
        for p in positions:
            rate_applied, spread_applied = mapping[p.id]
            rate = (
                (
                    p.signed_rate_pnl_per_bp * rate_bp
                    if p.asset_type == "swap"
                    else -p.base_market_value_usd * p.rate_duration * rate_bp / Decimal(10000)
                )
                if rate_applied
                else ZERO
            )
            spread = (
                -p.base_market_value_usd * p.spread_duration * spread_bp / Decimal(10000)
                if spread_applied
                else ZERO
            )
            rate, spread = (
                value.quantize(CENT, rounding=ROUND_HALF_EVEN) for value in (rate, spread)
            )
            total = (rate + spread).quantize(CENT)
            explanation = "; ".join(
                filter(
                    None,
                    (
                        "Signed swap USD/bp sensitivity"
                        if rate_applied and p.asset_type == "swap"
                        else "Cash rate-duration sensitivity"
                        if rate_applied
                        else "No matched rate shock",
                        "Matched corporate spread-duration sensitivity"
                        if spread_applied
                        else "No matched corporate spread shock",
                    ),
                )
            )
            results.append(
                PositionResult(
                    position_id=p.id,
                    base_market_value_usd=p.base_market_value_usd,
                    rate_applied=rate_applied,
                    spread_applied=spread_applied,
                    rate_pnl_usd=rate,
                    spread_pnl_usd=spread,
                    total_pnl_usd=total,
                    stressed_market_value_usd=p.base_market_value_usd + total,
                    explanation=explanation,
                )
            )
    return tuple(results)
