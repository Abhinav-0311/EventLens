import asyncio
import csv
import hmac
import io
from contextlib import asynccontextmanager
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException

from eventlens import __version__
from eventlens.config import Settings
from eventlens.errors import DomainError
from eventlens.finance import Portfolio, Scenario
from eventlens.schemas import (
    AnalysisResult,
    AnalyzeRequest,
    EventClass,
    EventDetail,
    EventPage,
    Health,
    Operation,
    ReplayRequest,
    SignalExport,
    utcnow,
)
from eventlens.sentiment import FinBert
from eventlens.service import RiskService
from eventlens.sources import Sources
from eventlens.store import Store
from eventlens.stress import RunPage, StressRequest, StressRun


class BodyLimitMiddleware:
    """Bound buffered request bytes, including bodies without Content-Length."""

    def __init__(self, app, maximum=65536):
        self.app, self.maximum = app, maximum

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chunks = []
        size = 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body = message.get("body", b"")
            size += len(body)
            if size > self.maximum:
                response = JSONResponse(
                    {
                        "error": {
                            "code": "REQUEST_TOO_LARGE",
                            "message": "Request body exceeds 64 KiB.",
                        }
                    },
                    status_code=413,
                )
                return await response(scope, receive, send)
            chunks.append(body)
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
            return await receive()

        return await self.app(scope, bounded_receive, send)


def create_app(settings: Settings | None = None, *, model=None, sources=None, clock=utcnow):
    settings = settings or Settings.from_environment()

    @asynccontextmanager
    async def lifespan(app):
        repository = Store(settings.database_path)
        await asyncio.to_thread(repository.initialize, clock())
        predictor = model if model is not None else FinBert(settings.model_cache)
        await asyncio.to_thread(predictor.load)
        adapters = sources if sources is not None else Sources(settings.source_limit)
        app.state.service = RiskService(settings, repository, predictor, adapters, clock)
        try:
            yield
        finally:
            await asyncio.to_thread(app.state.service.close)

    app = FastAPI(title="EventLens Risk Engine", version=__version__, lifespan=lifespan)
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-EventLens-Token"],
    )

    @app.middleware("http")
    async def host_guard(request, call_next):
        if request.url.hostname not in settings.allowed_hosts:
            return JSONResponse(
                {"error": {"code": "HOST_REJECTED", "message": "Host is not allowlisted."}},
                status_code=400,
            )
        response = await call_next(request)
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["cache-control"] = "no-store"
        return response

    @app.exception_handler(DomainError)
    async def domain_error(request, error):
        headers = {"retry-after": str(error.retry_after)} if error.retry_after else None
        return JSONResponse(
            {"error": {"code": error.code, "message": error.message}},
            status_code=error.status,
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse(
            {
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Request fields, values, or timestamps are invalid.",
                }
            },
            status_code=422,
        )

    @app.exception_handler(HTTPException)
    async def http_error(request, error):
        return JSONResponse(
            {
                "error": {
                    "code": "NOT_FOUND" if error.status_code == 404 else "HTTP_ERROR",
                    "message": "Requested resource is unavailable.",
                }
            },
            status_code=error.status_code,
        )

    @app.exception_handler(Exception)
    async def unexpected_error(request, error):
        return JSONResponse(
            {
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "Request failed; no internal details are exposed.",
                }
            },
            status_code=500,
        )

    def service(request: Request) -> RiskService:
        return request.app.state.service

    def authorize(request: Request):
        origin = request.headers.get("origin")
        accepted = {
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            str(request.base_url).rstrip("/"),
        }
        if origin and origin not in accepted:
            raise DomainError(
                "ORIGIN_REJECTED", "Cross-origin writes are not permitted from this origin.", 403
            )
        if settings.write_token and not hmac.compare_digest(
            request.headers.get("x-eventlens-token", ""), settings.write_token
        ):
            raise DomainError("WRITE_AUTH_REQUIRED", "A valid write token is required.", 401)

    Service = Annotated[RiskService, Depends(service)]
    Authorized = Annotated[None, Depends(authorize)]

    @app.get("/api/health", response_model=Health)
    def health(engine: Service):
        return engine.health()

    @app.post("/api/signals/analyze", response_model=AnalysisResult)
    def analyze(body: AnalyzeRequest, engine: Service, authorized: Authorized):
        return engine.analyze_user(body)

    @app.post("/api/ingestion/refresh", response_model=Operation, status_code=202)
    def refresh(engine: Service, authorized: Authorized):
        return engine.queue("refresh")

    @app.post("/api/ingestion/replay", response_model=Operation, status_code=202)
    def replay(body: ReplayRequest, engine: Service, authorized: Authorized):
        return engine.queue("replay", body.dataset)

    @app.get("/api/operations/{operation_id}", response_model=Operation)
    def operation(operation_id: str, engine: Service):
        result = engine.store.operation(operation_id)
        if result is None:
            raise DomainError("OPERATION_NOT_FOUND", "Operation does not exist.", 404)
        return result

    @app.get("/api/events", response_model=EventPage)
    def events(
        engine: Service,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
        event_class: EventClass | None = None,
        mode: Literal["live", "replay", "synthetic", "user"] | None = None,
        source_family: Literal["official_release", "social", "synthetic", "user"] | None = None,
        minimum_impact: Annotated[int, Query(ge=1, le=10)] = 1,
    ):
        return engine.list_events(limit, offset, event_class, mode, source_family, minimum_impact)

    @app.get("/api/events/{event_id}", response_model=EventDetail)
    def event(event_id: str, engine: Service):
        return engine.event_detail(event_id)

    @app.get("/api/portfolio", response_model=Portfolio)
    def portfolio(engine: Service):
        return engine.stress.portfolio

    @app.get("/api/scenarios", response_model=list[Scenario])
    def scenarios(engine: Service):
        return list(engine.stress.scenarios)

    @app.post("/api/stress-runs", response_model=StressRun, status_code=201)
    def manual_stress(body: StressRequest, engine: Service, authorized: Authorized):
        return engine.manual_stress(body)

    @app.get("/api/stress-runs", response_model=RunPage)
    def runs(
        engine: Service,
        limit: Annotated[int, Query(ge=1, le=100)] = 25,
        offset: Annotated[int, Query(ge=0, le=100000)] = 0,
        event_id: str | None = None,
    ):
        if event_id:
            engine.event_detail(event_id)
        return engine.store.list_runs(limit, offset, event_id)

    def require_run(engine, run_id):
        result = engine.store.stress_run(run_id)
        if result is None:
            raise DomainError("STRESS_RUN_NOT_FOUND", "Stress run does not exist.", 404)
        return result

    @app.get("/api/stress-runs/{run_id}", response_model=StressRun)
    def saved_run(run_id: str, engine: Service):
        return require_run(engine, run_id)

    @app.get(
        "/api/exports/stress-runs/{run_id}",
        response_model=StressRun,
        responses={200: {"content": {"text/csv": {}}}},
    )
    def export_run(run_id: str, engine: Service, format: Literal["json", "csv"] = "json"):
        run = require_run(engine, run_id)
        if format == "json":
            return run
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "run_id",
                "event_id",
                "signal_id",
                "mode",
                "portfolio_version",
                "scenario_id",
                "scenario_version",
                "impact",
                "rate_shock_bp",
                "spread_shock_bp",
                "position_id",
                "issuer",
                "asset_type",
                "base_market_value_usd",
                "rate_applied",
                "spread_applied",
                "rate_pnl_usd",
                "spread_pnl_usd",
                "total_pnl_usd",
                "stressed_market_value_usd",
            ]
        )
        positions = {p.id: p for p in run.portfolio_snapshot.positions}
        for result in run.position_results:
            position = positions[result.position_id]
            row = [
                run.id,
                run.event_id,
                run.signal_id,
                run.mode,
                run.portfolio_version,
                run.scenario_id,
                run.scenario_version,
                run.impact_score,
                run.actual_rate_shock_bp,
                run.actual_spread_shock_bp,
                result.position_id,
                position.issuer,
                position.asset_type,
                result.base_market_value_usd,
                result.rate_applied,
                result.spread_applied,
                result.rate_pnl_usd,
                result.spread_pnl_usd,
                result.total_pnl_usd,
                result.stressed_market_value_usd,
            ]
            writer.writerow(
                [
                    "'" + cell
                    if isinstance(cell, str)
                    and cell.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                    else cell
                    for cell in row
                ]
            )
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={
                "content-disposition": f'attachment; filename="eventlens-stress-{run.id}.csv"'
            },
        )

    @app.get(
        "/api/exports/signals",
        response_model=SignalExport,
        responses={200: {"content": {"text/csv": {}}}},
    )
    def exports(
        engine: Service, format: Literal["json", "csv"] = "json", event_id: str | None = None
    ):
        if event_id and engine.store.event_detail(event_id) is None:
            raise DomainError("EVENT_NOT_FOUND", "Event does not exist.", 404)
        results = engine.store.export_signals(event_id)
        if len(results) > 1000:
            raise DomainError(
                "EXPORT_TOO_LARGE", "Export exceeds 1,000 signals; select an event.", 413
            )
        if format == "json":
            return SignalExport(
                items=results, total=len(results), engine_version=engine.health().engine_version
            )
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        writer.writerow(
            [
                "signal_id",
                "event_id",
                "source_family",
                "provenance_mode",
                "publisher",
                "text",
                "sentiment_score",
                "event_class",
                "event_subtype",
                "impact_score",
                "review_reasons",
            ]
        )
        for result in results:
            row = [
                result.signal.id,
                result.signal.event_id,
                result.source.source_family,
                result.source.provenance_mode,
                result.source.publisher,
                result.source.text,
                result.signal.sentiment_score,
                result.signal.event_class,
                result.signal.event_subtype,
                result.signal.impact_score,
                "|".join(result.signal.review_reasons),
            ]
            # Prevent spreadsheet formula execution without changing the JSON evidence.
            writer.writerow(
                [
                    "'" + cell
                    if isinstance(cell, str)
                    and cell.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                    else cell
                    for cell in row
                ]
            )
        return Response(
            output.getvalue(),
            media_type="text/csv",
            headers={"content-disposition": 'attachment; filename="eventlens-signals.csv"'},
        )

    # Only the build output is public, never the repository or runtime directory.
    # Hash-based navigation needs no broad SPA fallback that could shadow the API.
    if (settings.frontend_directory / "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.frontend_directory, html=True))

    return app


app = create_app()
