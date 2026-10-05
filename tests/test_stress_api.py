import sqlite3
from datetime import timedelta
from decimal import Decimal as D

from conftest import NOW, FakeModel, FakeSources, await_operation, run_api

from eventlens.api import create_app


def app_for(settings, sources=None, clock=lambda: NOW):
    return create_app(settings, model=FakeModel(), sources=sources or FakeSources(), clock=clock)


def test_replay_auto_simulations_reconcile_and_survive_restart(settings):
    async def exercise(client):
        assert (await client.get("/api/health")).json()["portfolio_available"]
        portfolio = (await client.get("/api/portfolio")).json()
        assert len(portfolio["positions"]) == 20 and portfolio["base_total_usd"] == "100000000.00"
        assert len((await client.get("/api/scenarios")).json()) == 4
        for _ in range(2):
            operation = (await client.post("/api/ingestion/replay", json={})).json()
            assert (await await_operation(client, operation["id"]))["status"] == "completed"
        runs = (await client.get("/api/stress-runs")).json()
        assert runs["total"] == 3
        assert {r["scenario_id"] for r in runs["items"]} == {
            "monetary_tightening",
            "monetary_easing",
            "supply_disruption",
        }
        for run in runs["items"]:
            assert run["mode"] == "automatic_simulation" and run["simulation_clock"]
            assert all(not source["verified_publisher"] for source in run["source_snapshot"])
            assert D(run["base_total_usd"]) + D(run["total_pnl_usd"]) == D(
                run["stressed_total_usd"]
            )
            assert sum(D(p["total_pnl_usd"]) for p in run["position_results"]) == D(
                run["total_pnl_usd"]
            )
            detail = (await client.get(f"/api/events/{run['event_id']}")).json()
            assert run["id"] in detail["stress_run_ids"]
            assert detail["eligibility"]["state"] == "eligible_simulation"
            assert (
                await client.get(f"/api/exports/stress-runs/{run['id']}?format=csv")
            ).status_code == 200
        hike = next(r for r in runs["items"] if r["scenario_id"] == "monetary_tightening")
        assert hike["total_pnl_usd"] == "-2618000.00"
        return hike

    first = run_api(app_for(settings), exercise)

    async def reopen(client):
        saved = (await client.get(f"/api/stress-runs/{first['id']}")).json()
        assert saved == first
        assert (await client.get("/api/portfolio")).json()["base_total_usd"] == "100000000.00"

    run_api(app_for(settings), reopen)


def test_user_manual_requires_reason_is_idempotent_and_does_not_compound(settings):
    async def exercise(client):
        analyzed = (
            await client.post(
                "/api/signals/analyze", json={"text": "Aster Energy defaulted on its debt."}
            )
        ).json()
        event_id = analyzed["signal"]["event_id"]
        assert analyzed["signal"]["impact_score"] == 7
        assert (await client.get("/api/stress-runs")).json()["total"] == 0
        base = dict(
            event_id=event_id,
            scenario_id="credit_deterioration",
            idempotency_key="credit-comparison",
            impact_score=8,
        )
        assert (await client.post("/api/stress-runs", json=base)).status_code == 422
        body = base | {
            "override_reason": "Demonstrate issuer-specific spread widening; unverified fictional input."
        }
        first = (await client.post("/api/stress-runs", json=body)).json()
        repeated = (await client.post("/api/stress-runs", json=body)).json()
        assert first == repeated and first["mode"] == "manual_comparison"
        assert first["total_pnl_usd"] == "-1308000.00"
        assert len([p for p in first["position_results"] if p["spread_applied"]]) == 3
        assert "source_not_verified" in first["eligibility_snapshot"]["reasons"]
        conflict = await client.post("/api/stress-runs", json=body | {"impact_score": 10})
        assert (
            conflict.status_code == 409
            and conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
        )
        assert (
            await client.post("/api/stress-runs", json=body | {"mode": "automatic_live"})
        ).status_code == 422
        second = (
            await client.post("/api/stress-runs", json=body | {"idempotency_key": "credit-second"})
        ).json()
        assert second["id"] != first["id"] and second["base_total_usd"] == first["base_total_usd"]
        assert second["total_pnl_usd"] == first["total_pnl_usd"]
        assert (await client.get("/api/stress-runs?limit=1&offset=1")).json()["total"] == 2
        assert (await client.get("/api/portfolio")).json()["base_total_usd"] == first[
            "base_total_usd"
        ]

    run_api(app_for(settings), exercise)


def test_live_group_auto_once_and_conflicting_evidence_blocks(settings):
    async def exercise(client):
        operation = (await client.post("/api/ingestion/refresh")).json()
        assert (await await_operation(client, operation["id"]))["status"] == "completed"
        runs = (await client.get("/api/stress-runs")).json()
        assert runs["total"] == 1 and runs["items"][0]["mode"] == "automatic_live"
        assert len(runs["items"][0]["source_snapshot"]) == 2

    run_api(app_for(settings), exercise)

    class Conflicting(FakeSources):
        def fetch(self, source_id, now):
            records = super().fetch(source_id, now)
            if source_id == "fed_bluesky":
                records[0] = records[0].model_copy(
                    update={
                        "text": "The Federal Reserve lowered its policy rate by 50 basis points."
                    }
                )
            return records

    async def conflict(client):
        operation = (await client.post("/api/ingestion/refresh")).json()
        await await_operation(client, operation["id"])
        page = (await client.get("/api/events")).json()
        assert "cross_source_conflict" in page["items"][0]["eligibility"]["reasons"]
        assert (await client.get("/api/stress-runs")).json()[
            "total"
        ] == 1  # original historical run only

    run_api(app_for(settings, Conflicting(), clock=lambda: NOW + timedelta(minutes=6)), conflict)


def test_stale_future_and_unresolved_events_do_not_auto(settings):
    class Stale(FakeSources):
        def fetch(self, source_id, now):
            return [
                r.model_copy(update={"published_at": now - timedelta(days=4)})
                for r in super().fetch(source_id, now)
            ]

    async def exercise(client):
        operation = (await client.post("/api/ingestion/refresh")).json()
        await await_operation(client, operation["id"])
        assert (await client.get("/api/stress-runs")).json()["total"] == 0
        page = (await client.get("/api/events")).json()
        assert "stale_event" in page["items"][0]["eligibility"]["reasons"]
        for path in (
            "/api/stress-runs/unknown",
            "/api/exports/stress-runs/unknown",
            "/api/events/unknown",
        ):
            assert (await client.get(path)).status_code == 404
        assert (await client.get("/api/stress-runs?limit=999")).status_code == 422
        body = dict(
            event_id=page["items"][0]["id"],
            scenario_id="missing",
            idempotency_key="unknown-scenario",
            override_reason="Manual review",
        )
        assert (await client.post("/api/stress-runs", json=body)).status_code == 404

    run_api(app_for(settings, Stale()), exercise)


def test_version_one_database_migrates_without_losing_evidence(settings):
    async def seed(client):
        return (
            await client.post("/api/signals/analyze", json={"text": "A retained original input."})
        ).json()

    record = run_api(app_for(settings), seed)
    with sqlite3.connect(settings.database_path) as db:
        # This test owns its isolated database. Remove only the Phase 3 tables
        # to reconstruct an actual version-1 layout with retained event data.
        db.execute("DROP TABLE run_requests")
        db.execute("DROP TABLE stress_runs")
        db.execute("DROP TABLE snapshots")
        db.execute("PRAGMA user_version=1")

    async def reopen(client):
        assert (await client.get("/api/events")).json()["items"][0]["primary_signal"][
            "id"
        ] == record["signal"]["id"]

    run_api(app_for(settings), reopen)
    with sqlite3.connect(settings.database_path) as db:
        assert db.execute("PRAGMA user_version").fetchone()[0] == 2
