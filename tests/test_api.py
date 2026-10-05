import asyncio
from datetime import timedelta

import pytest
from conftest import NOW, FakeModel, FakeSources, await_operation, run_api

from eventlens.api import create_app
from eventlens.config import Settings
from eventlens.errors import DomainError


def app_for(settings, **kwargs):
    return create_app(
        settings,
        model=kwargs.pop("model", FakeModel()),
        sources=kwargs.pop("sources", FakeSources()),
        clock=lambda: NOW,
    )


def test_supplied_text_is_persisted_but_never_official(settings):
    async def scenario(client):
        body = {"text": "The Federal Reserve raised its policy rate by 50 basis points."}
        first = (await client.post("/api/signals/analyze", json=body)).json()
        assert first["signal"]["impact_score"] == 8
        assert first["source"]["provenance_mode"] == "user"
        assert not first["source"]["verified_publisher"]
        assert "source_not_verified" in first["signal"]["review_reasons"]
        second = (await client.post("/api/signals/analyze", json=body)).json()
        assert second["duplicate"]
        assert first["signal"]["id"] == second["signal"]["id"]
        page = (await client.get("/api/events")).json()
        assert page["total"] == 1
        event_id = page["items"][0]["id"]
        detail = (await client.get(f"/api/events/{event_id}")).json()
        assert len(detail["signals"]) == 1
        assert detail["stress_run_ids"] == []
        return first

    first = run_api(app_for(settings), scenario)

    async def after_restart(client):
        assert (await client.get("/api/events")).json()["items"][0]["primary_signal"][
            "id"
        ] == first["signal"]["id"]

    run_api(app_for(settings), after_restart)


def test_live_adapters_group_shared_release_without_independent_evidence(settings):
    async def scenario(client):
        response = await client.post("/api/ingestion/refresh")
        assert response.status_code == 202
        operation = await await_operation(client, response.json()["id"])
        assert operation["status"] == "completed"
        assert operation["result_counts"]["analyzed"] == 2
        page = (await client.get("/api/events")).json()
        assert page["total"] == 1
        event = page["items"][0]
        assert set(event["source_families"]) == {"official_release", "social"}
        assert event["verified_publisher_count"] == 1
        assert not event["evidence_independent"]
        assert "portfolio_not_configured" not in event["primary_signal"]["review_reasons"]
        assert event["eligibility"]["state"] == "eligible_live"
        retry = await client.post("/api/ingestion/refresh")
        assert retry.status_code == 429
        assert int(retry.headers["retry-after"]) > 0
        assert (await client.get("/api/health")).json()["sources"][0]["last_success_at"]

    run_api(app_for(settings), scenario)


def test_replay_is_explicit_synthetic_and_idempotent(settings):
    async def scenario(client):
        for _ in range(2):
            response = await client.post(
                "/api/ingestion/replay", json={"dataset": "synthetic_events"}
            )
            assert response.status_code == 202
            operation = await await_operation(client, response.json()["id"])
            assert operation["status"] == "completed"
        assert operation["result_counts"]["duplicates"] > 0
        page = (await client.get("/api/events", params={"mode": "synthetic"})).json()
        assert page["total"] > 0
        for item in page["items"]:
            assert item["primary_signal"]["simulation_clock"]
            assert item["verified_publisher_count"] == 0

    run_api(app_for(settings), scenario)


@pytest.mark.parametrize(
    "path, method, body, status",
    [
        ("/api/events/not-found", "GET", None, 404),
        ("/api/operations/not-found", "GET", None, 404),
        ("/api/signals/analyze", "POST", {"text": " "}, 422),
        ("/api/signals/analyze", "POST", {"text": "x", "verified_publisher": True}, 422),
        ("/api/ingestion/replay", "POST", {"dataset": "../../secret"}, 422),
        ("/api/events?limit=999", "GET", None, 422),
        ("/api/events?minimum_impact=11", "GET", None, 422),
    ],
)
def test_invalid_requests(settings, path, method, body, status):
    async def scenario(client):
        response = await client.request(method, path, json=body)
        assert response.status_code == status
        assert "error" in response.json()

    run_api(app_for(settings), scenario)


def test_model_unavailable_has_no_fallback(settings):
    model = FakeModel()
    model.ready, model.error_code = False, "MODEL_UNAVAILABLE"

    async def scenario(client):
        assert not (await client.get("/api/health")).json()["model_ready"]
        response = await client.post("/api/signals/analyze", json={"text": "Some text."})
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "MODEL_UNAVAILABLE"
        assert (await client.get("/api/events")).json()["total"] == 0

    run_api(app_for(settings, model=model), scenario)


def test_source_failure_is_recorded_and_keeps_previous_evidence(settings):
    class FailingSources(FakeSources):
        def fetch(self, source_id, now):
            raise DomainError("SOURCE_HTTP_ERROR", "Unavailable")

    async def seed(client):
        operation = (await client.post("/api/ingestion/refresh")).json()
        await await_operation(client, operation["id"])

    run_api(app_for(settings), seed)

    later_app = create_app(
        settings,
        model=FakeModel(),
        sources=FailingSources(),
        clock=lambda: NOW + timedelta(minutes=6),
    )

    async def fail(client):
        operation = (await client.post("/api/ingestion/refresh")).json()
        result = await await_operation(client, operation["id"])
        assert result["status"] == "failed"
        assert (await client.get("/api/events")).json()["total"] == 1
        health = (await client.get("/api/health")).json()
        assert all(s["stale"] and s["last_success_at"] for s in health["sources"])

    run_api(later_app, fail)


def test_public_writes_require_token(settings):
    secured = Settings(
        database_path=settings.database_path,
        public_mode=True,
        write_token="test-token-with-24-characters",
    )

    async def scenario(client):
        assert (await client.get("/api/health")).status_code == 200
        assert (
            await client.post("/api/signals/analyze", json={"text": "Some text."})
        ).status_code == 401
        allowed = await client.post(
            "/api/signals/analyze",
            json={"text": "Some text."},
            headers={"x-eventlens-token": secured.write_token},
        )
        assert allowed.status_code == 200

    run_api(app_for(secured), scenario)


def test_large_streamed_request_is_rejected(settings):
    async def payload():
        for _ in range(5):
            yield b"x" * 16000

    async def scenario(client):
        response = await client.post("/api/signals/analyze", content=payload())
        assert response.status_code == 413

    run_api(app_for(settings), scenario)


def test_signal_json_and_csv_exports(settings):
    async def scenario(client):
        await client.post("/api/signals/analyze", json={"text": "=SUM(A1:A2)"})
        json_response = await client.get("/api/exports/signals")
        assert json_response.json()["total"] == 1
        csv_response = await client.get("/api/exports/signals", params={"format": "csv"})
        assert "text/csv" in csv_response.headers["content-type"]
        assert "sentiment_score" in csv_response.text
        assert "'=SUM(A1:A2)" in csv_response.text

    run_api(app_for(settings), scenario)


def test_only_one_operation_is_queued(settings):
    import threading

    started, release = threading.Event(), threading.Event()

    class SlowSources(FakeSources):
        def fetch(self, source_id, now):
            started.set()
            assert release.wait(3)
            return super().fetch(source_id, now)

    async def scenario(client):
        first = await client.post("/api/ingestion/refresh")
        assert await asyncio.to_thread(started.wait, 2)
        try:
            second = await client.post("/api/ingestion/replay", json={})
            assert second.status_code == 409
        finally:
            release.set()
        await await_operation(client, first.json()["id"])

    run_api(app_for(settings, sources=SlowSources()), scenario)
