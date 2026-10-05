from collections import Counter
from decimal import Decimal as D

import pytest
from pydantic import ValidationError

from eventlens.finance import (
    Portfolio,
    Position,
    Scenario,
    calculate,
    load_assets,
    match_exposure,
    scaled_shocks,
)
from eventlens.schemas import Classification, EventClass, Impact


def classified(subtype, issuers=(), sectors=(), regions=("US",)):
    return Classification(
        event_class=EventClass.MACRO,
        event_subtype=subtype,
        assertion_status="asserted",
        impact_score=8,
        impact_components=Impact(magnitude_points=4, scope_points=3, rationale="test"),
        affected_issuers=list(issuers),
        affected_sectors=list(sectors),
        affected_regions=list(regions),
    )


def position(**changes):
    values = dict(
        id="test",
        asset_type="loan",
        instrument_type="fixed",
        issuer="Aster Energy",
        sector="energy",
        region="US",
        currency="USD",
        base_market_value_usd="1000000.00",
        notional_usd="1100000.00",
        rate_duration="4",
        spread_duration="3",
        signed_rate_pnl_per_bp="0",
        portfolio_version="test",
    )
    return Position.model_validate(values | changes)


def test_twenty_positions_and_fair_value_not_notional():
    portfolio, scenarios = load_assets()
    assert Counter(p.asset_type for p in portfolio.positions) == {"loan": 10, "bond": 6, "swap": 4}
    assert portfolio.base_total_usd == D("100000000.00")
    assert portfolio.notional_total_usd != portfolio.base_total_usd
    assert len(scenarios) == 4
    assert all(p.portfolio_version == portfolio.version for p in portfolio.positions)


@pytest.mark.parametrize(
    "rate,spread,expected",
    [
        (0, 0, "0"),
        (100, 0, "-40000"),
        (-100, 0, "40000"),
        (0, 200, "-60000"),
        (100, 200, "-100000"),
        (1, 0, "-400"),
    ],
)
def test_hand_computed_cash_position(rate, spread, expected):
    p = position()
    result = calculate((p,), {p.id: (True, True)}, D(rate), D(spread))[0]
    assert result.total_pnl_usd == D(expected)
    assert result.stressed_market_value_usd == p.base_market_value_usd + D(expected)


@pytest.mark.parametrize(
    "side,sensitivity,expected",
    [("payer_fixed", "250", "25000"), ("receiver_fixed", "-250", "-25000")],
)
def test_swap_signed_sensitivity_and_negative_fair_value(side, sensitivity, expected):
    p = position(
        asset_type="swap",
        instrument_type=side,
        base_market_value_usd="-50000",
        rate_duration="0",
        spread_duration="0",
        signed_rate_pnl_per_bp=sensitivity,
    )
    result = calculate((p,), {p.id: (True, False)}, D(100), D(200))[0]
    assert result.rate_pnl_usd == D(expected)
    assert result.spread_pnl_usd == 0
    assert result.stressed_market_value_usd == D("-50000") + D(expected)


def test_credit_does_not_spread_to_unrelated_same_sector_or_sovereign():
    portfolio, scenarios = load_assets()
    signal = classified("credit_deterioration", issuers=("Aster Energy",), sectors=("energy",))
    mapping = match_exposure(portfolio, scenarios[2], signal)
    assert all(not rate for rate, spread in mapping.values())
    matched = [p for p in portfolio.positions if mapping[p.id][1]]
    assert matched and all(p.issuer == "Aster Energy" and p.asset_type != "swap" for p in matched)
    assert all(not mapping[p.id][1] for p in portfolio.positions if p.sector == "sovereign")
    results = calculate(portfolio.positions, mapping, D(0), D(200))
    assert all(r.total_pnl_usd == 0 for r in results if not mapping[r.position_id][1])


def test_sector_match_and_geo_restricted_spread():
    portfolio, scenarios = load_assets()
    credit = match_exposure(
        portfolio, scenarios[2], classified("credit_deterioration", sectors=("transport",))
    )
    assert any(spread for rate, spread in credit.values())
    geo = match_exposure(
        portfolio, scenarios[3], classified("supply_disruption", sectors=("energy",))
    )
    for p in portfolio.positions:
        assert geo[p.id][1] == (p.sector == "energy" and p.asset_type != "swap")
    non_us = match_exposure(portfolio, scenarios[0], classified("rate_hike", regions=("EU",)))
    assert not any(rate or spread for rate, spread in non_us.values())


def test_scaling_rounding_reconciliation_and_independent_base():
    portfolio, scenarios = load_assets()
    assert scaled_shocks(scenarios[0], 10) == (D(125), D(0))
    assert scaled_shocks(scenarios[1], 8) == (D(-100), D(0))
    mapping = match_exposure(portfolio, scenarios[0], classified("rate_hike"))
    first = calculate(portfolio.positions, mapping, D(100), D(0))
    repeated = calculate(portfolio.positions, mapping, D(100), D(0))
    opposite = calculate(portfolio.positions, mapping, D(-100), D(0))
    assert first == repeated
    assert sum(r.stressed_market_value_usd for r in first) == portfolio.base_total_usd + sum(
        r.total_pnl_usd for r in first
    )
    assert sum(r.total_pnl_usd for r in first) == -sum(r.total_pnl_usd for r in opposite)
    assert portfolio.base_total_usd == D("100000000.00")
    p = position(base_market_value_usd="1.01", rate_duration="0.5", spread_duration="0.5")
    result = calculate((p,), {p.id: (True, True)}, D(100), D(100))[0]
    assert result.total_pnl_usd == result.rate_pnl_usd + result.spread_pnl_usd


@pytest.mark.parametrize(
    "changes",
    [
        dict(rate_duration="NaN"),
        dict(notional_usd="-1"),
        dict(base_market_value_usd="-1"),
        dict(rate_duration="1000"),
        dict(asset_type="swap", instrument_type="payer_fixed", signed_rate_pnl_per_bp="-1"),
        dict(sector="sovereign", spread_duration="1"),
    ],
)
def test_invalid_financial_inputs_rejected(changes):
    with pytest.raises(ValidationError):
        position(**changes)


@pytest.mark.parametrize("impact", [0, 11, True, 4.5])
def test_invalid_impact_scaling_rejected(impact):
    with pytest.raises(ValueError):
        scaled_shocks(load_assets()[1][0], impact)


@pytest.mark.parametrize(
    "changes",
    [
        dict(instrument_type="government"),
        dict(signed_rate_pnl_per_bp="1"),
        dict(asset_type="swap", instrument_type="payer_fixed", signed_rate_pnl_per_bp="1"),
        dict(
            asset_type="swap",
            instrument_type="receiver_fixed",
            rate_duration="0",
            spread_duration="0",
            signed_rate_pnl_per_bp="1",
        ),
    ],
)
def test_inconsistent_instrument_rejected(changes):
    with pytest.raises(ValidationError):
        position(**changes)


@pytest.mark.parametrize("change", ["duplicate", "wrong_version", "nonpositive"])
def test_portfolio_integrity(change):
    portfolio, _ = load_assets()
    values = portfolio.model_dump(exclude_computed_fields=True)
    if change == "duplicate":
        values["positions"] = [position(), position()]
        values["version"] = "test"
    elif change == "wrong_version":
        values["version"] = "different"
    else:
        values["positions"] = [
            position(
                asset_type="swap",
                instrument_type="receiver_fixed",
                base_market_value_usd="-1",
                rate_duration="0",
                spread_duration="0",
                signed_rate_pnl_per_bp="-1",
            )
        ]
        values["version"] = "test"
    with pytest.raises(ValidationError):
        Portfolio.model_validate(values)


@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_scenario_direction_cannot_be_silently_changed(index):
    scenario = load_assets()[1][index]
    values = scenario.model_dump() | {"rate_shock_bp": "0", "spread_shock_bp": "0"}
    with pytest.raises(ValidationError):
        Scenario.model_validate(values)


def test_nonfinite_shock_rejected_and_inputs_frozen():
    p = position()
    with pytest.raises(ValueError):
        calculate((p,), {p.id: (True, True)}, D("NaN"), D(0))
    with pytest.raises(ValidationError):
        p.base_market_value_usd = D(1)


def test_same_sector_unrelated_issuer_stays_untouched():
    base, scenarios = load_assets()
    other = position(
        id="OtherEnergy", issuer="Unrelated Fictional Energy", portfolio_version=base.version
    )
    portfolio = Portfolio.model_validate(
        base.model_dump(exclude={"positions"}, exclude_computed_fields=True)
        | {"positions": (*base.positions, other)}
    )
    mapping = match_exposure(
        portfolio,
        scenarios[2],
        classified("credit_deterioration", issuers=("Aster Energy",), sectors=("energy",)),
    )
    assert mapping[other.id] == (False, False)


def test_duplicate_scenario_file_rejected(tmp_path):
    import json
    import shutil

    from eventlens.config import ROOT

    for name in ("portfolio.csv", "portfolio.json", "scenarios.json"):
        shutil.copyfile(ROOT / "data" / name, tmp_path / name)
    scenarios = json.loads((tmp_path / "scenarios.json").read_text())
    (tmp_path / "scenarios.json").write_text(json.dumps(scenarios + [scenarios[0]]))
    with pytest.raises(ValueError, match="Duplicate scenario"):
        load_assets(tmp_path)
