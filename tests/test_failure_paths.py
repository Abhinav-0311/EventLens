from datetime import timedelta

import httpx
import pytest
from conftest import NOW, FakeModel, FakeSources, await_operation, run_api
from pydantic import ValidationError
from test_sources import RSS, social_feed

from eventlens.api import create_app
from eventlens.classification import classify
from eventlens.config import Settings
from eventlens.errors import DomainError
from eventlens.schemas import AnalyzeRequest, Operation, ReplayDataset, Sentiment
from eventlens.sources import Sources, canonical_release, make_record, parse_bluesky, parse_rss
from eventlens.store import Store


@pytest.mark.parametrize(
    "text,magnitude,subtype",
    [
        ("The FOMC raised its policy rate by 0.50 percentage points.", 4, "rate_hike"),
        ("The FOMC cut its policy rate by ¼ percentage point.", 3, "rate_cut"),
        ("The FOMC cut its policy rate by 10 basis points.", 2, "rate_cut"),
        ("The FOMC raised its policy rate by 0 basis points.", 0, "rate_hike"),
        ("The central bank raised its policy rate by 50 basis points.", 4, "rate_hike"),
        ("Aster Energy was downgraded.", 3, "credit_deterioration"),
        ("Global energy sector supply was disrupted.", 3, "supply_disruption"),
        ("Shipping supply was disrupted by war.", 4, "supply_disruption"),
        ("A company defaulted on its debt.", 5, "credit_deterioration"),
        ("US inflation increased.", 0, "macro_announcement"),
        ("War broke out.", 0, "geopolitical_event"),
    ],
)
def test_additional_rule_boundaries(text, magnitude, subtype):
    result = classify(text)
    assert result.event_subtype == subtype
    assert result.impact_components.magnitude_points == magnitude


def test_naive_timestamp_rejected():
    with pytest.raises(ValidationError):
        AnalyzeRequest(text="Some text", published_at="2026-10-05T00:00:00")


def test_multiple_same_direction_clauses_are_flagged():
    text = "The FOMC raised its policy rate by 50 basis points. The Federal Reserve raised its policy rate by 50 basis points."
    assert "multiple_event_clauses" in classify(text).flags


def test_unexpected_record_error_is_retained_and_does_not_expose_details(settings):
    class UnexpectedModel(FakeModel):
        def analyze(self, text):
            raise RuntimeError("Internal detail must not be exposed")

    async def scenario(client):
        response = await client.post("/api/signals/analyze", json={"text": "Some text"})
        assert response.status_code == 500
        assert "Internal detail" not in response.text

    run_api(create_app(settings, model=UnexpectedModel(), sources=FakeSources()), scenario)
    with Store(settings.database_path).connection() as db:
        assert (
            '"analysis_state":"failed"' in db.execute("SELECT body FROM sources").fetchone()["body"]
        )


@pytest.mark.parametrize(
    "probabilities",
    [
        {"positive": 1, "negative": 0},
        {"positive": float("nan"), "negative": 0, "neutral": 0},
        {"positive": 0.1, "negative": 0.1, "neutral": 0.1},
    ],
)
def test_invalid_probabilities_rejected(probabilities):
    with pytest.raises(ValidationError):
        Sentiment(
            score=0,
            probabilities=probabilities,
            model_id="test",
            model_revision="test",
            token_count=1,
            chunks=1,
        )


def test_invalid_settings_fail_closed():
    with pytest.raises(ValueError):
        Settings(public_mode=True)
    with pytest.raises(ValueError):
        Settings(source_limit=21)


def test_restart_marks_unfinished_operation_interrupted(settings):
    store = Store(settings.database_path)
    store.initialize(NOW)
    store.save_operation(
        Operation(id="unfinished", kind="refresh", status="running", started_at=NOW)
    )
    store.initialize(NOW + timedelta(minutes=1))
    result = store.operation("unfinished")
    assert result.status == "interrupted" and result.error_code == "PROCESS_RESTARTED"


def test_unsupported_schema_is_not_overwritten(settings):
    store = Store(settings.database_path)
    store.initialize(NOW)
    with store.connection() as db:
        db.execute("PRAGMA user_version=99")
    with pytest.raises(ValueError):
        store.initialize(NOW)
    with store.connection() as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 99


def test_stale_future_filters_and_exports(settings):
    async def scenario(client):
        text = "The Federal Reserve raised its policy rate by 50 basis points."
        future = (
            await client.post(
                "/api/signals/analyze",
                json={"text": text, "published_at": (NOW + timedelta(days=1)).isoformat()},
            )
        ).json()
        assert "future_publication" in future["signal"]["review_reasons"]
        old = (
            await client.post(
                "/api/signals/analyze",
                json={"text": text, "published_at": (NOW - timedelta(days=4)).isoformat()},
            )
        ).json()
        assert "stale_event" in old["signal"]["review_reasons"]
        assert "potential_text_duplicate" in old["signal"]["flags"]
        page = (
            await client.get(
                "/api/events",
                params={
                    "event_class": "Macroeconomic",
                    "source_family": "user",
                    "minimum_impact": 8,
                },
            )
        ).json()
        assert page["total"] == 2
        assert (
            await client.get("/api/exports/signals", params={"event_id": old["signal"]["event_id"]})
        ).json()["total"] == 1
        assert (
            await client.get("/api/exports/signals", params={"event_id": "missing"})
        ).status_code == 404

    run_api(
        create_app(settings, model=FakeModel(), sources=FakeSources(), clock=lambda: NOW), scenario
    )


def test_failed_inference_keeps_failed_input_without_signal(settings):
    class FailingModel(FakeModel):
        def analyze(self, text):
            raise DomainError("MODEL_INFERENCE_FAILED", "Failed")

    async def scenario(client):
        operation = (await client.post("/api/ingestion/refresh")).json()
        result = await await_operation(client, operation["id"])
        assert result["status"] == "failed" and result["result_counts"]["failed_records"] == 2
        assert (await client.get("/api/events")).json()["total"] == 0

    run_api(
        create_app(settings, model=FailingModel(), sources=FakeSources(), clock=lambda: NOW),
        scenario,
    )
    with Store(settings.database_path).connection() as db:
        rows = db.execute("SELECT body FROM sources").fetchall()
        assert len(rows) == 2 and all('"analysis_state":"failed"' in r["body"] for r in rows)


def test_missing_replay_fails_without_substitution(settings, tmp_path):
    broken = Settings(database_path=settings.database_path, replay_directory=tmp_path)

    async def scenario(client):
        operation = (await client.post("/api/ingestion/replay", json={})).json()
        assert (await await_operation(client, operation["id"]))["error_code"] == "REPLAY_INVALID"

    run_api(create_app(broken, model=FakeModel(), sources=FakeSources()), scenario)


def test_synthetic_dataset_cannot_claim_verified_events():
    with pytest.raises(ValidationError):
        ReplayDataset(
            provenance_mode="synthetic",
            simulation_clock=NOW,
            description="test",
            records=FakeSources().fetch("fed_rss", NOW),
        )


def test_simulation_clock_requires_timezone():
    record = (
        FakeSources()
        .fetch("fed_rss", NOW)[0]
        .model_copy(update={"provenance_mode": "synthetic", "verified_publisher": False})
    )
    with pytest.raises(ValidationError):
        ReplayDataset(
            provenance_mode="synthetic",
            simulation_clock=NOW.replace(tzinfo=None),
            description="test",
            records=[record],
        )


def test_cross_origin_writes_are_rejected(settings):
    async def scenario(client):
        response = await client.post(
            "/api/signals/analyze",
            json={"text": "Some text"},
            headers={"origin": "https://evil.test"},
        )
        assert response.status_code == 403

    run_api(create_app(settings, model=FakeModel(), sources=FakeSources()), scenario)


@pytest.mark.parametrize("status", [403, 500])
def test_http_retries_are_bounded(status):
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(status)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(DomainError):
            Sources(client=client, sleeper=lambda n: None).fetch("fed_rss", NOW)
    assert len(seen) == (1 if status == 403 else 2)


def test_network_retries_are_bounded():
    seen = []

    def respond(request):
        seen.append(request)
        raise httpx.ConnectError("Cannot connect", request=request)

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(DomainError) as error:
            Sources(client=client, sleeper=lambda n: None).fetch("fed_rss", NOW)
    assert error.value.code == "SOURCE_NETWORK_ERROR" and len(seen) == 2


@pytest.mark.parametrize("body", [b"{}", b"not-json"])
def test_bad_social_response_fails(body):
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=body))
    ) as client:
        with pytest.raises(DomainError):
            Sources(client=client).fetch("fed_bluesky", NOW)


def test_expansion_failure_retains_summary():
    def respond(request):
        return (
            httpx.Response(200, content=RSS)
            if str(request.url).endswith("press_all.xml")
            else httpx.Response(403)
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        record = Sources(client=client).fetch("fed_rss", NOW)[0]
    assert (
        "release_expansion_failed" in record.input_flags and record.text_kind == "headline_summary"
    )


def test_invalid_source_records_and_url():
    assert canonical_release("https://www.federalreserve.gov:bad/path") is None
    assert (
        parse_rss(
            b"<rss><channel><item><link>https://evil.test</link></item></channel></rss>", NOW, 5
        )
        == []
    )
    assert parse_bluesky(social_feed(text=""), NOW, 5) == []
    broken = social_feed()
    broken["feed"][0]["post"]["record"]["createdAt"] = "invalid"
    with pytest.raises(DomainError):
        parse_bluesky(broken, NOW, 5)


def test_source_truncation_is_explicit():
    record = make_record(
        source_id="fed_rss",
        family="official_release",
        uri="test",
        text="x" * 13000,
        kind="full_release",
        published=NOW,
        retrieved=NOW,
    )
    assert len(record.text) == 12000 and "source_text_truncated" in record.input_flags


def test_unknown_adapter_and_arbitrary_url_rejected():
    source = Sources()
    try:
        with pytest.raises(DomainError):
            source.fetch("unknown", NOW)
        with pytest.raises(DomainError):
            source._get("http://127.0.0.1/private")
    finally:
        source.close()
