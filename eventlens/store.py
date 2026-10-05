import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path

from eventlens.schemas import (
    AnalysisResult,
    EventDetail,
    EventPage,
    EventSummary,
    Operation,
    RiskSignal,
    SourceHealth,
    SourceRecord,
)


class Store:
    """Small synchronous SQLite repository; callers run outside the ASGI event loop."""

    def __init__(self, path: Path):
        self.path = path
        self._lock = threading.RLock()

    @contextmanager
    def connection(self):
        with self._lock:
            connection = sqlite3.connect(self.path, timeout=10)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            try:
                with connection:
                    yield connection
            finally:
                connection.close()

    def initialize(self, now):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            if db.execute("PRAGMA user_version").fetchone()[0] not in (0, 1, 2):
                raise ValueError("Unsupported database schema; existing data was not modified")
            db.execute("PRAGMA journal_mode = WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY, event_key TEXT UNIQUE NOT NULL,
                    grouping_method TEXT NOT NULL, primary_signal_id TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY, event_id TEXT REFERENCES events(id), body TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS signals (
                    id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id),
                    source_id TEXT NOT NULL REFERENCES sources(id), body TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS signals_event ON signals(event_id);
                CREATE INDEX IF NOT EXISTS sources_event ON sources(event_id);
                CREATE TABLE IF NOT EXISTS operations (id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS source_health (id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS snapshots (
                    kind TEXT NOT NULL, version TEXT NOT NULL, body TEXT NOT NULL,
                    PRIMARY KEY(kind, version)
                );
                CREATE TABLE IF NOT EXISTS stress_runs (
                    id TEXT PRIMARY KEY, event_id TEXT NOT NULL REFERENCES events(id),
                    automatic_key TEXT UNIQUE, body TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS stress_event ON stress_runs(event_id);
                CREATE TABLE IF NOT EXISTS run_requests (
                    idempotency_key TEXT PRIMARY KEY, request_hash TEXT NOT NULL,
                    run_id TEXT NOT NULL REFERENCES stress_runs(id)
                );
                PRAGMA user_version = 2;
            """)
            for row in db.execute("SELECT body FROM operations").fetchall():
                operation = Operation.model_validate_json(row["body"])
                if operation.status in {"queued", "running"}:
                    operation.status = "interrupted"
                    operation.error_code = "PROCESS_RESTARTED"
                    operation.completed_at = now
                    db.execute(
                        "UPDATE operations SET body=? WHERE id=?",
                        (operation.model_dump_json(), operation.id),
                    )

    def analysis(self, source_id: str, signal_id: str) -> AnalysisResult | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT r.body AS source_body, s.body AS signal_body FROM signals s "
                "JOIN sources r ON r.id=s.source_id WHERE r.id=? AND s.id=?",
                (source_id, signal_id),
            ).fetchone()
            if row:
                return AnalysisResult(
                    source=SourceRecord.model_validate_json(row["source_body"]),
                    signal=RiskSignal.model_validate_json(row["signal_body"]),
                    duplicate=True,
                )
        return None

    @staticmethod
    def _priority(source: SourceRecord, signal: RiskSignal):
        return (
            source.verified_publisher,
            {"full_release": 3, "headline_summary": 2, "post": 1, "supplied_text": 0}[
                source.text_kind
            ],
            signal.created_at,
        )

    def save_analysis(self, source: SourceRecord, signal: RiskSignal, key: str, grouping: str):
        with self.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO events VALUES (?, ?, ?, NULL, ?)",
                (signal.event_id, key, grouping, signal.created_at.isoformat()),
            )
            db.execute(
                "INSERT INTO sources VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET event_id=excluded.event_id, body=excluded.body",
                (source.id, signal.event_id, source.model_dump_json()),
            )
            db.execute(
                "INSERT OR IGNORE INTO signals VALUES (?, ?, ?, ?)",
                (signal.id, signal.event_id, source.id, signal.model_dump_json()),
            )
            current = db.execute(
                "SELECT s.body AS signal_body, r.body AS source_body FROM events e "
                "JOIN signals s ON s.id=e.primary_signal_id JOIN sources r ON r.id=s.source_id WHERE e.id=?",
                (signal.event_id,),
            ).fetchone()
            if current is None or self._priority(source, signal) >= self._priority(
                SourceRecord.model_validate_json(current["source_body"]),
                RiskSignal.model_validate_json(current["signal_body"]),
            ):
                db.execute(
                    "UPDATE events SET primary_signal_id=? WHERE id=?", (signal.id, signal.event_id)
                )

    def save_failed_source(self, source: SourceRecord, code: str):
        source = source.model_copy(update={"analysis_state": "failed", "error_code": code})
        with self.connection() as db:
            # Never replace an already analyzed historical record with a failed retry.
            db.execute(
                "INSERT INTO sources VALUES (?, NULL, ?) ON CONFLICT(id) DO UPDATE SET body=excluded.body "
                "WHERE json_extract(sources.body, '$.analysis_state')!='analyzed'",
                (source.id, source.model_dump_json()),
            )

    def save_received_source(self, source: SourceRecord):
        with self.connection() as db:
            db.execute(
                "INSERT OR IGNORE INTO sources VALUES (?, NULL, ?)",
                (source.id, source.model_dump_json()),
            )

    def potential_duplicate(self, source: SourceRecord, event_id: str) -> bool:
        with self.connection() as db:
            return (
                db.execute(
                    "SELECT 1 FROM sources WHERE event_id IS NOT NULL AND event_id!=? "
                    "AND json_extract(body, '$.content_hash')=? LIMIT 1",
                    (event_id, source.content_hash),
                ).fetchone()
                is not None
            )

    def _summary(self, db, row) -> EventSummary:
        records = [
            SourceRecord.model_validate_json(r["body"])
            for r in db.execute(
                "SELECT body FROM sources WHERE event_id=? ORDER BY id", (row["id"],)
            ).fetchall()
        ]
        signals = [
            RiskSignal.model_validate_json(r["body"])
            for r in db.execute(
                "SELECT body FROM signals WHERE event_id=?", (row["id"],)
            ).fetchall()
        ]
        publishers = {
            r.publisher for r in records if r.verified_publisher and r.provenance_mode == "live"
        }
        asserted = {
            s.event_subtype
            for s in signals
            if s.assertion_status == "asserted" and s.event_subtype != "unknown"
        }
        flags = ["cross_source_conflict"] if len(asserted) > 1 else []
        return EventSummary(
            id=row["id"],
            canonical_event_key=row["event_key"],
            grouping_method=row["grouping_method"],
            source_record_ids=[r.id for r in records],
            primary_signal=RiskSignal.model_validate_json(row["signal_body"]),
            source_families=sorted({r.source_family for r in records}),
            provenance_modes=sorted({r.provenance_mode for r in records}),
            verified_publisher_count=len(publishers),
            evidence_independent=len(publishers) > 1,
            review_flags=flags,
        )

    def list_events(
        self, limit=25, offset=0, event_class=None, mode=None, source_family=None, minimum_impact=1
    ):
        clauses = ["json_extract(s.body, '$.impact_score')>=?"]
        params = [minimum_impact]
        if event_class:
            clauses.append("json_extract(s.body, '$.event_class')=?")
            params.append(str(event_class))
        for name, value in (("provenance_mode", mode), ("source_family", source_family)):
            if value:
                clauses.append(
                    f"EXISTS (SELECT 1 FROM sources r WHERE r.event_id=e.id AND json_extract(r.body, '$.{name}')=?)"
                )
                params.append(value)
        where = " AND ".join(clauses)
        # Column identifiers are fixed above; all user values use SQLite binding.
        join = " FROM events e JOIN signals s ON s.id=e.primary_signal_id WHERE " + where
        with self.connection() as db:
            count = db.execute("SELECT count(*)" + join, params).fetchone()[0]
            rows = db.execute(
                "SELECT e.*, s.body AS signal_body"
                + join
                + " ORDER BY e.created_at DESC, e.id LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            return EventPage(
                items=[self._summary(db, row) for row in rows],
                total=count,
                limit=limit,
                offset=offset,
            )

    def event_detail(self, event_id: str) -> EventDetail | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT e.*, s.body AS signal_body FROM events e JOIN signals s ON s.id=e.primary_signal_id WHERE e.id=?",
                (event_id,),
            ).fetchone()
            if row is None:
                return None
            return EventDetail(
                event=self._summary(db, row),
                evidence=[
                    SourceRecord.model_validate_json(r["body"])
                    for r in db.execute(
                        "SELECT body FROM sources WHERE event_id=? ORDER BY id", (event_id,)
                    ).fetchall()
                ],
                signals=[
                    RiskSignal.model_validate_json(r["body"])
                    for r in db.execute(
                        "SELECT body FROM signals WHERE event_id=? ORDER BY id", (event_id,)
                    ).fetchall()
                ],
                stress_run_ids=[
                    r["id"]
                    for r in db.execute(
                        "SELECT id FROM stress_runs WHERE event_id=? ORDER BY id", (event_id,)
                    ).fetchall()
                ],
            )

    def save_snapshot(self, kind, version, body):
        with self.connection() as db:
            row = db.execute(
                "SELECT body FROM snapshots WHERE kind=? AND version=?", (kind, version)
            ).fetchone()
            if row and row["body"] != body:
                raise ValueError(
                    "Snapshot contents changed without a new version; existing history was preserved"
                )
            db.execute("INSERT OR IGNORE INTO snapshots VALUES (?, ?, ?)", (kind, version, body))

    def stress_run(self, run_id):
        from eventlens.stress import StressRun

        with self.connection() as db:
            row = db.execute("SELECT body FROM stress_runs WHERE id=?", (run_id,)).fetchone()
            return StressRun.model_validate_json(row["body"]) if row else None

    def automatic_run(self, identity):
        from eventlens.stress import StressRun

        with self.connection() as db:
            row = db.execute(
                "SELECT body FROM stress_runs WHERE automatic_key=?", (identity,)
            ).fetchone()
            return StressRun.model_validate_json(row["body"]) if row else None

    def idempotent_run(self, key, request_hash):
        from eventlens.errors import DomainError
        from eventlens.stress import StressRun

        with self.connection() as db:
            row = db.execute(
                "SELECT q.request_hash, r.body FROM run_requests q JOIN stress_runs r ON r.id=q.run_id WHERE q.idempotency_key=?",
                (key,),
            ).fetchone()
            if row and row["request_hash"] != request_hash:
                raise DomainError(
                    "IDEMPOTENCY_CONFLICT",
                    "Idempotency key was already used for a different request.",
                    409,
                )
            return StressRun.model_validate_json(row["body"]) if row else None

    def save_run(self, run, automatic_key=None, idempotency_key=None, request_hash=None):
        # Checks and insertion share a repository lock and a transaction. A crash
        # cannot leave a partially saved result or bind a retry to a missing run.
        with self.connection() as db:
            if automatic_key:
                previous = self.automatic_run(automatic_key)
                if previous:
                    return previous
            if idempotency_key:
                previous = self.idempotent_run(idempotency_key, request_hash)
                if previous:
                    return previous
            db.execute(
                "INSERT INTO stress_runs VALUES (?, ?, ?, ?)",
                (
                    run.id,
                    run.event_id,
                    automatic_key,
                    run.model_dump_json(exclude_computed_fields=True),
                ),
            )
            if idempotency_key:
                db.execute(
                    "INSERT INTO run_requests VALUES (?, ?, ?)",
                    (idempotency_key, request_hash, run.id),
                )
        return run

    def list_runs(self, limit=25, offset=0, event_id=None):
        from eventlens.stress import RunPage, StressRun

        with self.connection() as db:
            where, params = (" WHERE event_id=?", [event_id]) if event_id else ("", [])
            count = db.execute("SELECT count(*) FROM stress_runs" + where, params).fetchone()[0]
            rows = db.execute(
                "SELECT body FROM stress_runs"
                + where
                + " ORDER BY json_extract(body, '$.created_at') DESC, id LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
            return RunPage(
                items=[StressRun.model_validate_json(row["body"]) for row in rows],
                total=count,
                limit=limit,
                offset=offset,
            )

    def save_operation(self, operation: Operation):
        with self.connection() as db:
            db.execute(
                "INSERT INTO operations VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                (operation.id, operation.model_dump_json()),
            )

    def operation(self, operation_id: str) -> Operation | None:
        with self.connection() as db:
            row = db.execute("SELECT body FROM operations WHERE id=?", (operation_id,)).fetchone()
            return Operation.model_validate_json(row["body"]) if row else None

    def save_source_health(self, health: SourceHealth):
        with self.connection() as db:
            db.execute(
                "INSERT INTO source_health VALUES (?, ?) ON CONFLICT(id) DO UPDATE SET body=excluded.body",
                (health.source_id, health.model_dump_json()),
            )

    def source_health(self, source_id: str) -> SourceHealth:
        with self.connection() as db:
            row = db.execute("SELECT body FROM source_health WHERE id=?", (source_id,)).fetchone()
            return (
                SourceHealth.model_validate_json(row["body"])
                if row
                else SourceHealth(source_id=source_id)
            )

    def export_signals(self, event_id: str | None = None):
        with self.connection() as db:
            query = "SELECT s.body AS signal_body, r.body AS source_body FROM signals s JOIN sources r ON r.id=s.source_id"
            params = []
            if event_id:
                query += " WHERE s.event_id=?"
                params.append(event_id)
            query += " ORDER BY s.id LIMIT 1001"
            rows = db.execute(query, params).fetchall()
            return [
                AnalysisResult(
                    source=SourceRecord.model_validate_json(row["source_body"]),
                    signal=RiskSignal.model_validate_json(row["signal_body"]),
                )
                for row in rows
            ]
