import pytest

from eventlens.classification import classify


@pytest.mark.parametrize(
    "text, subtype, impact, status",
    [
        (
            "The Federal Reserve raised its policy rate by 50 basis points.",
            "rate_hike",
            8,
            "asserted",
        ),
        ("The Federal Reserve cut its policy rate by 25 basis points.", "rate_cut", 7, "asserted"),
        (
            "The FOMC decided to lower the target range by 1/2 percentage point.",
            "rate_cut",
            8,
            "asserted",
        ),
        (
            "The Federal Reserve raised its policy rate by 75 basis points.",
            "rate_hike",
            9,
            "asserted",
        ),
        (
            "The Federal Reserve may raise its policy rate by 50 basis points.",
            "rate_hike",
            8,
            "speculative",
        ),
        (
            "The Federal Reserve did not raise its policy rate by 50 basis points.",
            "rate_hike",
            1,
            "negated",
        ),
        ("Aster Energy defaulted on its debt.", "credit_deterioration", 7, "asserted"),
        ("Aster Energy did not default on its debt.", "credit_deterioration", 1, "negated"),
        ("Aster Energy launched a new product.", "product_launch", 3, "asserted"),
        ("Aster Energy acquired Meridian Transport.", "acquisition", 5, "asserted"),
        ("Global oil supply was disrupted by war.", "supply_disruption", 9, "asserted"),
        ("A birthday party will take place on Tuesday.", "unknown", 1, "unclear"),
        ("The company raised its product prices by 50 percent.", "unknown", 1, "unclear"),
    ],
)
def test_supported_rules(text, subtype, impact, status):
    result = classify(text)
    assert result.event_subtype == subtype
    assert result.impact_score == impact
    assert result.assertion_status == status
    assert result.classification_method == "phrase_rules_v2"
    assert 1 <= result.impact_score <= 10
    for span in result.evidence_spans:
        assert text[span.start : span.end] == span.text


def test_historical_policy_clause_is_not_a_current_hike():
    result = classify(
        "Last year the Federal Reserve raised its policy rate by 75 basis points. "
        "Today the FOMC decided to lower the target range by 25 basis points."
    )
    assert result.event_subtype == "rate_cut"
    assert result.impact_score == 7
    assert "historical_context_ignored" in result.flags


def test_conflicting_current_decisions_require_review():
    result = classify(
        "The Federal Reserve raised its policy rate by 50 basis points. "
        "The FOMC cut its policy rate by 25 basis points."
    )
    assert result.event_subtype == "ambiguous"
    assert "conflicting_events" in result.flags


def test_missing_policy_magnitude_does_not_invent_severity():
    result = classify("The Federal Reserve raised its policy rate.")
    assert result.impact_score <= 7
    assert "magnitude_unspecified" in result.flags


def test_online_publication_is_not_global_scope():
    result = classify("Aster Energy defaulted on its debt. This was posted online.")
    assert result.impact_components.scope_points == 1


def test_rate_action_cannot_jump_over_unrelated_budget_text():
    result = classify(
        "The Federal Reserve raised its staffing budget while leaving its policy rate unchanged by 50 basis points."
    )
    assert result.event_subtype != "rate_hike"


def test_plural_interest_rates_are_recognized():
    assert (
        classify("The Federal Reserve raised interest rates by 50 basis points.").impact_score == 8
    )


@pytest.mark.parametrize(
    "object_text", ["software configuration", "account settings", "display preferences"]
)
def test_default_requires_a_financial_obligation(object_text):
    result = classify(f"Global Aster Energy defaulted on its {object_text}, not a debt obligation.")
    assert result.event_subtype == "unknown"
    assert result.impact_score == 1
    assert result.assertion_status == "unclear"


@pytest.mark.parametrize("amount,bp", [("a quarter", 25), ("one half", 50), ("three quarters", 75)])
def test_worded_policy_amounts(amount, bp):
    result = classify(f"The FOMC lowered its policy rate by {amount} percentage point.")
    assert result.impact_score == {25: 7, 50: 8, 75: 9}[bp]
    assert "magnitude_unspecified" not in result.flags


def test_policy_hold_is_informational_not_an_asserted_shock():
    result = classify("The Federal Reserve left its policy rate unchanged.")
    assert result.event_class.value == "Macroeconomic"
    assert result.event_subtype == "macro_announcement"
    assert result.assertion_status == "unclear"
    assert result.impact_score == 1
