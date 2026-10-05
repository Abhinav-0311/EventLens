"""Real cached FinBERT -> replay -> stress -> export -> restart, with optional live fetch."""

import argparse
import asyncio
import csv
import io
import json
import sys
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from phase2_verify import operation

from eventlens.api import create_app
from eventlens.config import ROOT, Settings
from eventlens.schemas import utcnow


async def verify(live):
    proof_id = uuid4().hex
    settings = Settings(
        database_path=ROOT / "runtime" / f"phase3-verification-{proof_id}.sqlite3", source_limit=20
    )
    app = create_app(settings)
    report = {"started_at": utcnow().isoformat(), "live_requested": live}
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            health = (await client.get("/api/health")).json()
            assert health["model_ready"] and health["portfolio_available"]
            report["model_revision"] = health["model_revision"]
            portfolio = (await client.get("/api/portfolio")).json()
            assert (
                portfolio["base_total_usd"] == "100000000.00" and len(portfolio["positions"]) == 20
            )
            report["replay_operation"] = await operation(client, "/api/ingestion/replay", {})
            before = (await client.get("/api/stress-runs")).json()
            assert before["total"] == 3
            report["repeat_operation"] = await operation(client, "/api/ingestion/replay", {})
            after = (await client.get("/api/stress-runs")).json()
            assert (
                before == after and report["repeat_operation"]["result_counts"]["stress_runs"] == 0
            )
            outcomes = {r["scenario_id"]: r["total_pnl_usd"] for r in before["items"]}
            assert outcomes["monetary_tightening"] == "-2618000.00"
            assert outcomes["monetary_easing"] == "2618000.00"
            for run in before["items"]:
                assert run["mode"] == "automatic_simulation"
                assert run["signal_snapshot"]["sentiment_model_id"] == "ProsusAI/finbert"
                assert Decimal(run["base_total_usd"]) + Decimal(run["total_pnl_usd"]) == Decimal(
                    run["stressed_total_usd"]
                )
                exported = (await client.get(f"/api/exports/stress-runs/{run['id']}")).json()
                assert exported == run
                response = await client.get(f"/api/exports/stress-runs/{run['id']}?format=csv")
                rows = list(csv.DictReader(io.StringIO(response.text)))
                assert len(rows) == 20
                assert sum(Decimal(row["total_pnl_usd"]) for row in rows) == Decimal(
                    run["total_pnl_usd"]
                )
            events = (await client.get("/api/events?mode=synthetic&limit=100")).json()["items"]
            credit = next(
                e for e in events if e["primary_signal"]["event_subtype"] == "credit_deterioration"
            )
            assert (
                credit["primary_signal"]["impact_score"] == 7
                and credit["eligibility"]["state"] == "informational"
            )
            body = {
                "event_id": credit["id"],
                "scenario_id": "credit_deterioration",
                "idempotency_key": "real-model-credit-comparison",
                "impact_score": 8,
                "override_reason": "Fictional issuer-specific comparison at impact 8; original signal remains impact 7.",
            }
            response = await client.post("/api/stress-runs", json=body)
            response.raise_for_status()
            manual = response.json()
            assert (
                manual["total_pnl_usd"] == "-1308000.00" and manual["mode"] == "manual_comparison"
            )
            assert (await client.post("/api/stress-runs", json=body)).json() == manual
            assert (
                await client.post("/api/stress-runs", json=body | {"impact_score": 10})
            ).status_code == 409
            report["automatic_simulation_outcomes_usd"] = outcomes
            report["manual_credit_pnl_usd"] = manual["total_pnl_usd"]
            report["idempotency_and_exports_passed"] = True
            if live:
                report["live_operation"] = await operation(client, "/api/ingestion/refresh")
                page = (await client.get("/api/events?mode=live&limit=100")).json()
                assert report["live_operation"]["result_counts"]["successful_sources"] == 2
                report["live_event_count"] = page["total"]
                report["live_eligibility_states"] = {
                    state: sum(e["eligibility"]["state"] == state for e in page["items"])
                    for state in {e["eligibility"]["state"] for e in page["items"]}
                }
            saved = (await client.get("/api/stress-runs?limit=100")).json()
            assert (await client.get("/api/portfolio")).json() == portfolio
            report["base_unchanged_passed"] = True
            report["saved_run_count"] = saved["total"]
    reopened = create_app(settings)
    async with reopened.router.lifespan_context(reopened):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=reopened), base_url="http://localhost"
        ) as client:
            assert (await client.get("/api/stress-runs?limit=100")).json() == saved
            assert (await client.get("/api/portfolio")).json() == portfolio
            report["restart_snapshot_persistence_passed"] = True
    report["completed_at"] = utcnow().isoformat()
    report["database"] = str(settings.database_path.relative_to(ROOT))
    report_path = ROOT / "runtime" / f"phase3-proof-{proof_id}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report | {"proof_file": str(report_path.relative_to(ROOT))}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also fetch both actual providers; no fixture substitution.",
    )
    asyncio.run(verify(parser.parse_args().live))
