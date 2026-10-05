import hashlib
import logging
import math
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

from eventlens.classification import classify
from eventlens.config import ENGINE_VERSION, MODEL_ID, MODEL_REVISION, Settings
from eventlens.errors import DomainError
from eventlens.schemas import (
    AnalysisResult,
    AnalyzeRequest,
    Health,
    Operation,
    ReplayDataset,
    RiskSignal,
    SourceRecord,
    digest,
    utcnow,
)
from eventlens.sources import SOURCE_IDS, canonical_release
from eventlens.stress import StressEngine, StressRequest

logger = logging.getLogger(__name__)
SUPPORTED = {"rate_hike", "rate_cut", "credit_deterioration", "supply_disruption"}


class RiskService:
    def __init__(self, settings: Settings, store, model, sources, clock=utcnow):
        self.settings, self.store, self.model, self.sources, self.clock = (
            settings,
            store,
            model,
            sources,
            clock,
        )
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="eventlens-ingestion")
        self._gate = threading.Lock()
        self._active_id = None
        self._analyzing = False
        self._closed = False
        self.stress = StressEngine(store, settings, clock)

    def close(self):
        with self._gate:
            self._closed = True
        self._executor.shutdown(wait=True)
        self.sources.close()

    def health(self) -> Health:
        now = self.clock()
        sources = [self.store.source_health(source_id) for source_id in SOURCE_IDS]
        for source in sources:
            source.stale = (
                source.error_code is not None
                or source.last_success_at is None
                or (now - source.last_success_at).total_seconds()
                > self.settings.refresh_interval_seconds * 2
            )
        return Health(
            status="ready"
            if self.model.ready and all(not s.stale for s in sources)
            else "degraded",
            model_ready=self.model.ready,
            model_id=MODEL_ID,
            model_revision=MODEL_REVISION,
            model_error_code=self.model.error_code,
            engine_version=ENGINE_VERSION,
            sources=sources,
            portfolio_available=True,
        )

    def event_detail(self, event_id):
        return self.stress.detail(event_id)

    def list_events(self, *args):
        page = self.store.list_events(*args)
        for item in page.items:
            item.eligibility = self.stress.detail(item.id).eligibility
        return page

    def manual_stress(self, request: StressRequest):
        with self._gate:
            if self._closed or self._active_id or self._analyzing:
                raise DomainError(
                    "ENGINE_BUSY", "The engine is processing another request; retry shortly.", 409
                )
            self._analyzing = True
        try:
            return self.stress.manual(request)
        finally:
            with self._gate:
                self._analyzing = False

    def _require_model(self):
        if not self.model.ready:
            raise DomainError(
                "MODEL_UNAVAILABLE",
                "Pinned local model is unavailable; no prediction was generated.",
            )

    def analyze_user(self, request: AnalyzeRequest) -> AnalysisResult:
        self._require_model()
        with self._gate:
            if self._active_id or self._analyzing or self._closed:
                raise DomainError(
                    "ENGINE_BUSY", "The engine is processing another request; retry shortly.", 409
                )
            self._analyzing = True
        try:
            now = self.clock()
            text_hash = hashlib.sha256(request.text.encode()).hexdigest()
            source = SourceRecord(
                id="pending",
                source_id="supplied_text",
                source_family="user",
                publisher="User-supplied text",
                canonical_uri="user://" + digest(request.text, str(request.published_at)),
                text=request.text,
                text_kind="supplied_text",
                published_at=request.published_at or now,
                retrieved_at=now,
                provenance_mode="user",
                language="und",
                content_hash=text_hash,
                verified_publisher=False,
            )
            return self._process(source)
        finally:
            with self._gate:
                self._analyzing = False

    def _process(self, source: SourceRecord, simulation_clock=None) -> AnalysisResult:
        content_hash = hashlib.sha256(source.text.encode()).hexdigest()
        source = source.model_copy(
            update={
                "content_hash": content_hash,
                "id": digest(
                    source.source_id,
                    source.publisher,
                    source.canonical_uri,
                    source.provenance_mode,
                    str(simulation_clock),
                    content_hash,
                ),
            }
        )
        release = (
            canonical_release(source.linked_release_url or "")
            if source.verified_publisher
            else None
        )
        key = ":".join(
            (
                source.provenance_mode,
                str(simulation_clock),
                source.publisher,
                release or source.canonical_uri,
            )
        )
        grouping = "linked_official_release" if release else "publisher_and_canonical_uri"
        event_id = digest(key)
        signal_id = digest(source.id, ENGINE_VERSION, MODEL_REVISION)
        cached = self.store.analysis(source.id, signal_id)
        if cached:
            return cached
        self.store.save_received_source(source)
        try:
            classification = classify(source.text)
            sentiment = self.model.analyze(source.text)
            flags = list(classification.flags) + source.input_flags
            if sentiment.truncated:
                flags.append("sentiment_truncated")
            if self.store.potential_duplicate(source, event_id):
                flags.append("potential_text_duplicate")
            reasons = list(flags)
            if classification.impact_score <= 7:
                reasons.append("impact_not_above_threshold")
            if classification.event_subtype not in SUPPORTED:
                reasons.append("scenario_unsupported")
            if classification.assertion_status != "asserted":
                reasons.append("event_not_asserted")
            if not source.verified_publisher:
                reasons.append("source_not_verified")
            if source.provenance_mode != "live":
                reasons.append("non_live_mode")
            reference = simulation_clock or self.clock()
            age = reference - source.published_at
            if age.total_seconds() < 0:
                reasons.append("future_publication")
            elif age.total_seconds() > self.settings.live_max_age_hours * 3600:
                reasons.append("stale_event")
            signal = RiskSignal(
                **classification.model_dump(exclude={"flags"}),
                flags=sorted(set(flags)),
                id=signal_id,
                event_id=event_id,
                source_record_id=source.id,
                sentiment_score=sentiment.score,
                sentiment_probabilities=sentiment.probabilities,
                sentiment_model_id=sentiment.model_id,
                model_revision=sentiment.model_revision,
                inference_mode=sentiment.inference_mode,
                sentiment_token_count=sentiment.token_count,
                sentiment_chunks=sentiment.chunks,
                sentiment_truncated=sentiment.truncated,
                engine_version=ENGINE_VERSION,
                created_at=self.clock(),
                simulation_clock=simulation_clock,
                review_reasons=sorted(set(reasons)),
                stress_readiness="needs_review"
                if classification.impact_score > 7
                else "informational",
            )
            source = source.model_copy(update={"analysis_state": "analyzed", "error_code": None})
            self.store.save_analysis(source, signal, key, grouping)
            return AnalysisResult(source=source, signal=signal)
        except DomainError as error:
            self.store.save_failed_source(source, error.code)
            raise
        except Exception as error:
            logger.exception("Record analysis failed: %s", source.id)
            self.store.save_failed_source(source, "RECORD_ANALYSIS_FAILED")
            raise DomainError(
                "RECORD_ANALYSIS_FAILED", "Input analysis failed; retained for review.", 500
            ) from error

    def queue(self, kind: str, dataset="synthetic_events") -> Operation:
        self._require_model()
        with self._gate:
            if self._closed or self._active_id or self._analyzing:
                raise DomainError(
                    "ENGINE_BUSY",
                    "Only one ingestion or analysis operation may run at a time.",
                    409,
                )
            if kind == "refresh":
                now = self.clock()
                due = [
                    self.store.source_health(source_id).next_allowed_at for source_id in SOURCE_IDS
                ]
                if all(d is not None and d > now for d in due):
                    seconds = max(1, math.ceil(min((d - now).total_seconds() for d in due)))
                    raise DomainError(
                        "REFRESH_COOLDOWN", "Source refresh cooldown is active.", 429, seconds
                    )
            operation = Operation(
                id=uuid4().hex, kind=kind, status="queued", started_at=self.clock()
            )
            self.store.save_operation(operation)
            self._active_id = operation.id
            self._executor.submit(self._run, operation, dataset)
            return operation

    def _run(self, operation: Operation, dataset: str):
        touched_events = set()
        counts = {
            "analyzed": 0,
            "duplicates": 0,
            "failed_records": 0,
            "successful_sources": 0,
            "failed_sources": 0,
            "skipped_sources": 0,
            "stress_runs": 0,
        }
        try:
            operation.status = "running"
            self.store.save_operation(operation)
            if operation.kind == "replay":
                if dataset != "synthetic_events":
                    raise DomainError("REPLAY_UNKNOWN", "Replay dataset is not allowlisted.", 404)
                try:
                    replay = ReplayDataset.model_validate_json(
                        (self.settings.replay_directory / "synthetic_events.json").read_text(
                            encoding="utf-8"
                        )
                    )
                except (OSError, ValueError) as error:
                    raise DomainError(
                        "REPLAY_INVALID", "Saved replay dataset is unavailable or invalid."
                    ) from error
                self._process_records(
                    replay.records, counts, replay.simulation_clock, touched_events
                )
            else:
                for source_id in SOURCE_IDS:
                    now = self.clock()
                    health = self.store.source_health(source_id)
                    if health.next_allowed_at and health.next_allowed_at > now:
                        counts["skipped_sources"] += 1
                        continue
                    health.last_attempt_at = now
                    health.next_allowed_at = now + timedelta(
                        seconds=self.settings.refresh_interval_seconds
                    )
                    self.store.save_source_health(health)
                    try:
                        records = self.sources.fetch(source_id, now)
                        health.last_success_at = self.clock()
                        health.record_count = len(records)
                        health.error_code = None
                        counts["successful_sources"] += 1
                        failed_before = counts["failed_records"]
                        self._process_records(records, counts, touched_events=touched_events)
                        if counts["failed_records"] > failed_before:
                            health.error_code = "RECORD_ANALYSIS_FAILED"
                    except DomainError as error:
                        counts["failed_sources"] += 1
                        health.error_code = error.code
                        if error.retry_after:
                            health.next_allowed_at = max(
                                health.next_allowed_at, now + timedelta(seconds=error.retry_after)
                            )
                    finally:
                        self.store.save_source_health(health)
                if not counts["successful_sources"]:
                    raise DomainError("SOURCES_UNAVAILABLE", "No source could be refreshed.")
            # Wait for the complete batch: the second adapter may contradict the
            # first. Incomplete/failed batches never start an automatic run.
            if not any(
                counts[key] for key in ("failed_records", "failed_sources", "skipped_sources")
            ):
                mode = "automatic_simulation" if operation.kind == "replay" else "automatic_live"
                for event_id in sorted(touched_events):
                    before = len(self.store.event_detail(event_id).stress_run_ids)
                    run = self.stress.automatic(event_id, mode)
                    if run and len(self.store.event_detail(event_id).stress_run_ids) > before:
                        counts["stress_runs"] += 1
            operation.status = "completed" if counts["failed_records"] == 0 else "failed"
            if counts["failed_records"]:
                operation.error_code = "RECORD_ANALYSIS_FAILED"
        except DomainError as error:
            operation.status, operation.error_code = "failed", error.code
        except Exception:
            logger.exception("Ingestion operation failed: %s", operation.id)
            operation.status, operation.error_code = "failed", "OPERATION_FAILED"
        finally:
            operation.result_counts, operation.completed_at = counts, self.clock()
            try:
                self.store.save_operation(operation)
            finally:
                with self._gate:
                    self._active_id = None

    def _process_records(self, records, counts, simulation_clock=None, touched_events=None):
        for source in records:
            try:
                result = self._process(source, simulation_clock)
                counts["duplicates" if result.duplicate else "analyzed"] += 1
                if touched_events is not None:
                    touched_events.add(result.signal.event_id)
            except DomainError:
                counts["failed_records"] += 1
