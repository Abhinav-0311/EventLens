from datetime import timedelta
from io import BytesIO
from types import SimpleNamespace

import pytest
from conftest import NOW, FakeModel, FakeSources, await_operation, run_api

from eventlens.api import create_app
from eventlens.config import Settings
from eventlens.errors import DomainError
from eventlens.schemas import AnalyzeRequest
from eventlens.sentiment import FinBert, aggregate_probabilities
from eventlens.service import RiskService
from eventlens.store import Store


def test_host_and_origin_guards(settings):
    async def scenario(client):
        rejected = await client.get("/api/health", headers={"host": "evil.test"})
        assert rejected.status_code == 400 and rejected.json()["error"]["code"] == "HOST_REJECTED"
        accepted = await client.post(
            "/api/signals/analyze",
            json={"text": "Some text"},
            headers={"origin": "http://localhost"},
        )
        assert accepted.status_code == 200
        assert accepted.headers["cache-control"] == "no-store"

    run_api(create_app(settings, model=FakeModel(), sources=FakeSources()), scenario)


def test_wildcard_host_configuration_rejected():
    with pytest.raises(ValueError):
        Settings(allowed_hosts=("*",))


def test_empty_prediction_aggregation_rejected():
    with pytest.raises(ValueError):
        aggregate_probabilities([], [])


def test_corrupt_model_cache_cannot_load():
    class WrongWeights:
        def __truediv__(self, part):
            return self

        def is_file(self):
            return True

        def stat(self):
            return SimpleNamespace(st_size=437_992_753)

        def open(self, mode):
            return BytesIO(b"incorrect weight contents")

    model = FinBert(WrongWeights())
    model.load()
    assert not model.ready and model.error_code == "MODEL_UNAVAILABLE"


def test_closed_worker_rejects_submissions(settings):
    store = Store(settings.database_path)
    store.initialize(NOW)
    service = RiskService(settings, store, FakeModel(), FakeSources(), lambda: NOW)
    service.close()
    from eventlens.errors import DomainError

    with pytest.raises(DomainError):
        service.queue("replay")
    with pytest.raises(DomainError):
        service.analyze_user(AnalyzeRequest(text="Some text"))


def test_unexpected_job_failure_does_not_leave_engine_busy(settings, monkeypatch):
    app = create_app(settings, model=FakeModel(), sources=FakeSources(), clock=lambda: NOW)

    async def scenario(client):
        store = app.state.service.store
        original = store.save_operation
        failed = False

        def save(operation):
            nonlocal failed
            if operation.status == "running" and not failed:
                failed = True
                raise RuntimeError("Simulated storage interruption")
            return original(operation)

        monkeypatch.setattr(store, "save_operation", save)
        first = (await client.post("/api/ingestion/replay", json={})).json()
        result = await await_operation(client, first["id"])
        assert result["error_code"] == "OPERATION_FAILED"
        second = await client.post("/api/ingestion/replay", json={})
        assert second.status_code == 202
        assert (await await_operation(client, second.json()["id"]))["status"] == "completed"

    run_api(app, scenario)


def test_truncated_sentiment_is_a_visible_review_reason(settings):
    class TruncatedModel(FakeModel):
        def analyze(self, text):
            return super().analyze(text).model_copy(update={"truncated": True})

    async def scenario(client):
        response = await client.post(
            "/api/signals/analyze",
            json={"text": "The FOMC raised its policy rate by 50 basis points."},
        )
        signal = response.json()["signal"]
        assert signal["sentiment_truncated"]
        assert "sentiment_truncated" in signal["review_reasons"]

    run_api(create_app(settings, model=TruncatedModel(), sources=FakeSources()), scenario)


def test_per_source_retry_after_survives_restart_and_skips_not_due_adapter(settings):
    clock = [NOW]

    class RateLimitedSources(FakeSources):
        def fetch(self, source_id, now):
            if source_id == "fed_bluesky":
                raise DomainError("SOURCE_RATE_LIMITED", "Retry later", retry_after=600)
            return super().fetch(source_id, now)

    async def first(client):
        operation = (await client.post("/api/ingestion/refresh")).json()
        result = await await_operation(client, operation["id"])
        assert result["result_counts"]["successful_sources"] == 1
        assert result["result_counts"]["failed_sources"] == 1
        assert (await client.get("/api/health")).json()["status"] == "degraded"

    run_api(
        create_app(
            settings, model=FakeModel(), sources=RateLimitedSources(), clock=lambda: clock[0]
        ),
        first,
    )
    clock[0] += timedelta(seconds=301)

    async def second(client):
        operation = (await client.post("/api/ingestion/refresh")).json()
        result = await await_operation(client, operation["id"])
        assert result["result_counts"]["skipped_sources"] == 1
        assert result["result_counts"]["successful_sources"] == 1
        social = next(
            s
            for s in (await client.get("/api/health")).json()["sources"]
            if s["source_id"] == "fed_bluesky"
        )
        assert social["next_allowed_at"] == "2026-10-05T00:10:00Z"

    run_api(
        create_app(
            settings, model=FakeModel(), sources=RateLimitedSources(), clock=lambda: clock[0]
        ),
        second,
    )
