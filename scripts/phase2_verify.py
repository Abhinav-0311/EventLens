"""Exercise the real backend and cached model; --live also calls both source adapters."""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from eventlens.api import create_app
from eventlens.config import ROOT, Settings
from eventlens.schemas import utcnow


async def operation(client, path, body=None):
    response = await client.post(path, json=body)
    response.raise_for_status()
    operation_id = response.json()["id"]
    for _ in range(1200):
        result = (await client.get(f"/api/operations/{operation_id}")).json()
        if result["status"] not in {"running", "queued"}:
            assert result["status"] == "completed", result
            return result
        await asyncio.sleep(0.1)
    raise AssertionError("Operation exceeded the 120-second verification deadline")


async def verify(live, source_limit=5):
    run_id = uuid4().hex
    settings = Settings(
        database_path=ROOT / "runtime" / f"verification-{run_id}.sqlite3", source_limit=source_limit
    )
    app = create_app(settings)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://localhost"
        ) as client:
            health = (await client.get("/api/health")).json()
            assert health["model_ready"], health
            first = await operation(
                client, "/api/ingestion/replay", {"dataset": "synthetic_events"}
            )
            before = (
                await client.get("/api/events", params={"mode": "synthetic", "limit": 100})
            ).json()
            repeated = await operation(
                client, "/api/ingestion/replay", {"dataset": "synthetic_events"}
            )
            after = (
                await client.get("/api/events", params={"mode": "synthetic", "limit": 100})
            ).json()
            assert first["result_counts"]["analyzed"] == 9
            assert repeated["result_counts"]["duplicates"] == 9
            # Current eligibility includes a fresh evaluation timestamp; compare
            # immutable evidence/signals rather than this deliberately live clock.
            stable_before = [
                {k: v for k, v in e.items() if k != "eligibility"} for e in before["items"]
            ]
            stable_after = [
                {k: v for k, v in e.items() if k != "eligibility"} for e in after["items"]
            ]
            assert stable_before == stable_after and after["total"] == 8
            response = await client.post(
                "/api/signals/analyze",
                json={"text": "The company defaulted on its debt and reported substantial losses."},
            )
            response.raise_for_status()
            signal = response.json()["signal"]
            assert (
                signal["sentiment_model_id"] == "ProsusAI/finbert" and signal["sentiment_score"] < 0
            )
            assert "source_not_verified" in signal["review_reasons"]
            report = {
                "checked_at": utcnow().isoformat(),
                "model_revision": health["model_revision"],
                "database": str(settings.database_path.relative_to(ROOT)),
                "replay_operation": first,
                "repeated_replay_operation": repeated,
                "synthetic_event_count": after["total"],
                "replay_idempotent": stable_before == stable_after,
                "supplied_negative_score": signal["sentiment_score"],
                "synthetic_results": [
                    {
                        "subtype": e["primary_signal"]["event_subtype"],
                        "impact": e["primary_signal"]["impact_score"],
                        "assertion": e["primary_signal"]["assertion_status"],
                    }
                    for e in after["items"]
                ],
            }
            if live:
                report["live_operation"] = await operation(client, "/api/ingestion/refresh")
                live_events = (
                    await client.get("/api/events", params={"mode": "live", "limit": 100})
                ).json()
                families = {family for e in live_events["items"] for family in e["source_families"]}
                assert {"official_release", "social"} <= families, families
                assert report["live_operation"]["result_counts"]["successful_sources"] == 2
                report["live_event_count"] = live_events["total"]
                report["live_source_families"] = sorted(families)
                report["independent_publishers_claimed"] = any(
                    e["evidence_independent"] for e in live_events["items"]
                )
            exported = await client.get("/api/exports/signals")
            exported.raise_for_status()
            assert (
                await client.get("/api/exports/signals", params={"format": "csv"})
            ).status_code == 200
            assert (await client.get("/api/events/unknown-id")).status_code == 404
            assert (
                await client.post("/api/signals/analyze", json={"text": " "})
            ).status_code == 422
            report["exported_signal_count"] = exported.json()["total"]
            report["full_release_records"] = sum(
                item["source"]["text_kind"] == "full_release" for item in exported.json()["items"]
            )
            report["health"] = (await client.get("/api/health")).json()
            expected_count = (await client.get("/api/events")).json()["total"]
    # Reopen the same database in a fresh application lifecycle, without refetching sources.
    reopened = create_app(settings)
    async with reopened.router.lifespan_context(reopened):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=reopened), base_url="http://localhost"
        ) as client:
            actual_count = (await client.get("/api/events")).json()["total"]
            assert actual_count == expected_count
            report["restart_persistence_passed"] = True
    report_path = ROOT / "runtime" / f"phase2-proof-{run_id}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="Contact configured public sources; never replace failures with fixtures.",
    )
    parser.add_argument("--source-limit", type=int, default=5, choices=range(1, 21))
    arguments = parser.parse_args()
    asyncio.run(verify(arguments.live, arguments.source_limit))
