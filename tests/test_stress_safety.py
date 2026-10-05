from datetime import timedelta
from decimal import Decimal as D

import pytest
from conftest import NOW, RELEASE, FakeModel, FakeSources, await_operation, run_api
from pydantic import ValidationError

from eventlens.api import create_app
from eventlens.errors import DomainError
from eventlens.finance import calculate
from eventlens.schemas import AnalyzeRequest
from eventlens.service import RiskService
from eventlens.store import Store
from eventlens.stress import StressRequest


@pytest.fixture
def service(settings):
    store = Store(settings.database_path)
    store.initialize(NOW)
    engine = RiskService(settings, store, FakeModel(), FakeSources(), lambda: NOW)
    yield engine
    engine.close()


def seed(engine, text="The Federal Reserve raised its policy rate by 50 basis points.", **changes):
    source = FakeSources().fetch("fed_rss", NOW)[0].model_copy(update={"text": text} | changes)
    return engine._process(source)


@pytest.mark.parametrize(
    "changes,reason",
    [
        ({"published_at": NOW + timedelta(days=1)}, "future_publication"),
        ({"language": "und"}, "language_requires_review"),
        ({"input_flags": ["source_text_truncated"]}, "source_text_truncated"),
        ({"verified_publisher": False}, "source_not_verified"),
    ],
)
def test_unsafe_source_never_automatically_runs(service, changes, reason):
    result = seed(service, **changes)
    assert reason in service.event_detail(result.signal.event_id).eligibility.reasons
    assert service.stress.automatic(result.signal.event_id, "automatic_live") is None
    assert service.store.list_runs().total == 0


def test_negated_conflict_in_same_group_blocks_before_auto(service):
    result = seed(service)
    source = (
        FakeSources()
        .fetch("fed_bluesky", NOW)[0]
        .model_copy(
            update={"text": "The Federal Reserve did not raise its policy rate by 50 basis points."}
        )
    )
    service._process(source)
    assert (
        "cross_source_conflict" in service.event_detail(result.signal.event_id).eligibility.reasons
    )
    assert service.stress.automatic(result.signal.event_id, "automatic_live") is None


def test_no_credit_and_supply_exposure_is_reviewable(service):
    for text, reason in [
        ("Global financials sector defaulted on its debt.", None),
        ("A mystery issuer defaulted on its debt.", "no_matching_exposure"),
        ("Global supply was disrupted by war.", "supply_exposure_unresolved"),
    ]:
        result = seed(service, text, canonical_uri=RELEASE + "?" + text)
        detail = service.event_detail(result.signal.event_id)
        if reason:
            assert reason in detail.eligibility.reasons
        else:
            assert detail.eligibility.spread_position_ids
        if reason:
            request = StressRequest(
                event_id=result.signal.event_id,
                scenario_id=detail.eligibility.scenario_id,
                idempotency_key="no-exposure-compare",
                override_reason="Illustrative manual review",
            )
            with pytest.raises(DomainError, match="No eligible"):
                service.manual_stress(request)


def test_verified_source_does_not_make_a_software_default_a_credit_event(service):
    result = seed(
        service,
        "Global Aster Energy defaulted on its software configuration, not a financial obligation.",
    )
    assert result.signal.event_subtype == "unknown"
    assert result.signal.impact_score == 1
    assert service.stress.automatic(result.signal.event_id, "automatic_live") is None
    assert service.store.list_runs().total == 0


def test_truncated_model_and_speculation_are_review_only(service):
    analyze = service.model.analyze
    service.model.analyze = lambda text: analyze(text).model_copy(update={"truncated": True})
    result = seed(service)
    assert "sentiment_truncated" in service.event_detail(result.signal.event_id).eligibility.reasons
    assert service.stress.automatic(result.signal.event_id, "automatic_live") is None
    speculative = seed(
        service,
        "The Federal Reserve may raise its policy rate by 50 basis points.",
        canonical_uri="https://www.federalreserve.gov/newsevents/pressreleases/monetary20261003a.htm",
        linked_release_url=None,
    )
    assert (
        "event_not_asserted"
        in service.event_detail(speculative.signal.event_id).eligibility.reasons
    )
    assert service.stress.automatic(speculative.signal.event_id, "automatic_live") is None


def test_automatic_and_storage_retries_return_same_snapshot(service):
    result = seed(service)
    first = service.stress.automatic(result.signal.event_id, "automatic_live")
    second = service.stress.automatic(result.signal.event_id, "automatic_live")
    assert first == second
    with service.store.connection() as db:
        identity = db.execute(
            "SELECT automatic_key FROM stress_runs WHERE id=?", (first.id,)
        ).fetchone()[0]
    assert service.store.save_run(first, automatic_key=identity) == first
    manual = StressRequest(
        event_id=result.signal.event_id,
        scenario_id="monetary_easing",
        idempotency_key="opposite-comparison",
        override_reason="Compare the opposite direction explicitly.",
    )
    run = service.manual_stress(manual)
    assert run.total_pnl_usd == -first.total_pnl_usd
    with service.store.connection() as db:
        request_hash = db.execute("SELECT request_hash FROM run_requests").fetchone()[0]
    assert (
        service.store.save_run(
            run, idempotency_key=manual.idempotency_key, request_hash=request_hash
        )
        == run
    )
    assert service.store.list_runs(event_id=result.signal.event_id).total == 2


def test_different_family_and_blank_reason_rejected(service):
    result = seed(service)
    with pytest.raises(ValidationError):
        StressRequest(
            event_id=result.signal.event_id,
            scenario_id="monetary_tightening",
            idempotency_key="blank-reason",
            override_reason="         ",
        )
    request = StressRequest(
        event_id=result.signal.event_id,
        scenario_id="credit_deterioration",
        idempotency_key="wrong-family",
        override_reason="Deliberately wrong family",
    )
    with pytest.raises(DomainError, match="does not match"):
        service.manual_stress(request)


def test_failed_math_does_not_save_run_or_mutate_base(service, monkeypatch):
    result = seed(service)
    original = service.stress.portfolio.base_total_usd

    def inconsistent(*args):
        rows = calculate(*args)
        return (rows[0].model_copy(update={"total_pnl_usd": D(123)}), *rows[1:])

    monkeypatch.setattr("eventlens.stress.calculate", inconsistent)
    request = StressRequest(
        event_id=result.signal.event_id,
        scenario_id="monetary_tightening",
        idempotency_key="failed-calculation",
        override_reason="Demonstrate failed calculation isolation",
    )
    with pytest.raises(DomainError, match="do not reconcile"):
        service.manual_stress(request)
    assert service.store.list_runs().total == 0
    assert service.stress.portfolio.base_total_usd == original
    assert service.analyze_user(AnalyzeRequest(text="Engine gate was released."))


def test_immutable_version_reuse_rejected_without_overwrite(service):
    with pytest.raises(ValueError, match="new version"):
        service.store.save_snapshot("portfolio", service.stress.portfolio.version, "changed")
    with service.store.connection() as db:
        assert (
            db.execute("SELECT body FROM snapshots WHERE kind='portfolio'").fetchone()[0]
            == service.stress.portfolio.snapshot_json()
        )


def test_request_storage_failure_rolls_back_entire_run(service):
    import sqlite3

    result = seed(service)
    with service.store.connection() as db:
        db.execute(
            "CREATE TRIGGER controlled_request_failure BEFORE INSERT ON run_requests BEGIN SELECT RAISE(ABORT, 'controlled fixture failure'); END"
        )
    request = StressRequest(
        event_id=result.signal.event_id,
        scenario_id="monetary_tightening",
        idempotency_key="rollback-request",
        override_reason="Test atomic rollback of run and request",
    )
    with pytest.raises(sqlite3.IntegrityError):
        service.manual_stress(request)
    assert service.store.list_runs().total == 0
    assert service.store.idempotent_run(request.idempotency_key, "unused") is None
    assert not service._analyzing
    assert service.stress.portfolio.base_total_usd == D("100000000.00")


def test_busy_manual_admission_and_partial_batch_block(settings):
    class Partial(FakeSources):
        def fetch(self, source_id, now):
            if source_id == "fed_bluesky":
                raise DomainError("SOURCE_HTTP_ERROR", "Controlled failure")
            return super().fetch(source_id, now)

    app = create_app(settings, model=FakeModel(), sources=Partial(), clock=lambda: NOW)

    async def exercise(client):
        result = (
            await client.post(
                "/api/signals/analyze",
                json={"text": "The Federal Reserve raised its policy rate by 50 basis points."},
            )
        ).json()
        body = dict(
            event_id=result["signal"]["event_id"],
            scenario_id="monetary_tightening",
            idempotency_key="busy-manual-test",
            override_reason="Explicit manual comparison",
        )
        app.state.service._analyzing = True
        try:
            assert (await client.post("/api/stress-runs", json=body)).status_code == 409
        finally:
            app.state.service._analyzing = False
        operation = (await client.post("/api/ingestion/refresh")).json()
        await await_operation(client, operation["id"])
        assert (await client.get("/api/stress-runs")).json()["total"] == 0
        assert (
            await client.get("/api/stress-runs?event_id=" + result["signal"]["event_id"])
        ).status_code == 200

    run_api(app, exercise)
