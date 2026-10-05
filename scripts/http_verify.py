"""Start an owned localhost server, exercise real HTTP, and stop that server afterward."""

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx

from eventlens.config import ROOT
from eventlens.schemas import utcnow


def main():
    with socket.socket() as bound:
        bound.bind(("127.0.0.1", 0))
        port = bound.getsockname()[1]
    run_id = uuid4().hex
    environment = os.environ.copy()
    environment.update(
        EVENTLENS_DATABASE=str(ROOT / "runtime" / f"http-verification-{run_id}.sqlite3"),
        EVENTLENS_PUBLIC="false",
        EVENTLENS_WRITE_TOKEN="local-verification-token-24chars",
        EVENTLENS_ALLOWED_HOSTS="127.0.0.1,localhost",
    )
    server = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "eventlens.api:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--workers",
            "1",
        ],
        cwd=ROOT,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    try:
        with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=25) as client:
            deadline = time.monotonic() + 90
            while True:
                if server.poll() is not None:
                    raise RuntimeError("Owned server exited before readiness")
                try:
                    health = client.get("/api/health")
                    if health.status_code == 200:
                        break
                except httpx.HTTPError:
                    pass
                if time.monotonic() > deadline:
                    raise RuntimeError("Owned server did not become ready within 90 seconds")
                time.sleep(0.2)
            assert health.json()["model_ready"]
            assert client.get("/openapi.json").status_code == 200
            assert client.get("/docs").status_code == 200
            body = {"text": "The Federal Reserve raised its policy rate by 50 basis points."}
            assert client.post("/api/signals/analyze", json=body).status_code == 401
            headers = {
                "x-eventlens-token": environment["EVENTLENS_WRITE_TOKEN"],
                "origin": f"http://127.0.0.1:{port}",
            }
            response = client.post("/api/signals/analyze", json=body, headers=headers)
            response.raise_for_status()
            result = response.json()
            assert result["signal"]["impact_score"] == 8
            assert result["source"]["provenance_mode"] == "user"
            assert not result["source"]["verified_publisher"]
            assert client.get("/api/events").json()["total"] == 1
            assert client.get("/api/events/not-found").status_code == 404
            assert (
                client.post("/api/signals/analyze", json={"text": " "}, headers=headers).status_code
                == 422
            )
            assert client.get("/api/portfolio").json()["base_total_usd"] == "100000000.00"
            stress_body = {
                "event_id": result["signal"]["event_id"],
                "scenario_id": "monetary_tightening",
                "idempotency_key": "http-stress-comparison",
                "override_reason": "Unverified text: explicit illustrative comparison.",
            }
            assert client.post("/api/stress-runs", json=stress_body).status_code == 401
            stress_response = client.post("/api/stress-runs", json=stress_body, headers=headers)
            stress_response.raise_for_status()
            stress_run = stress_response.json()
            assert stress_run["total_pnl_usd"] == "-2618000.00"
            assert (
                client.post("/api/stress-runs", json=stress_body, headers=headers).json()
                == stress_run
            )
            assert (
                client.get(f"/api/exports/stress-runs/{stress_run['id']}?format=csv").status_code
                == 200
            )
            assert client.get("/api/stress-runs").json()["total"] == 1
            report = {
                "checked_at": utcnow().isoformat(),
                "real_http_passed": True,
                "openapi_and_docs_passed": True,
                "write_auth_passed": True,
                "same_origin_write_passed": True,
                "stress_http_auth_idempotency_export_passed": True,
                "stress_pnl_usd": stress_run["total_pnl_usd"],
                "port": port,
                "impact_score": result["signal"]["impact_score"],
                "sentiment_score": result["signal"]["sentiment_score"],
                "model_revision": result["signal"]["model_revision"],
            }
            (ROOT / "runtime" / f"http-proof-{run_id}.json").write_text(
                json.dumps(report, indent=2), encoding="utf-8"
            )
            print(json.dumps(report, indent=2))
    finally:
        server.terminate()
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)


if __name__ == "__main__":
    main()
