"""Serial CPU diagnostics. Corpus text is deliberately excluded from result reports."""

import argparse
import hashlib
import json
import platform
import statistics
import sys
import time
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from eventlens.classification import classify
from eventlens.config import ENGINE_VERSION, MODEL_REVISION, MODEL_SHA256, ROOT, Settings
from eventlens.evaluation import SENTIMENT_LABELS, classification_metrics, nearest_rank
from eventlens.schemas import EventClass, utcnow
from eventlens.sentiment import FinBert


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def timing(values):
    return {
        "median_ms": statistics.median(values),
        "p95_ms": nearest_rank(values, 0.95),
        "n": len(values),
    }


def events(cases, model):
    rows, times = [], []
    keys = ("event_class", "event_subtype", "assertion_status", "impact_score")
    for case in cases:
        started = time.perf_counter()
        prediction = classify(case["text"])
        rule_ms = (time.perf_counter() - started) * 1000
        started = time.perf_counter()
        sentiment = model.analyze(case["text"])
        times.append((time.perf_counter() - started) * 1000)
        actual = prediction.model_dump(mode="json")
        expected = {key: case[key] for key in keys}
        mismatch = [key for key in keys if actual[key] != expected[key]]
        unsafe = (
            (
                case["assertion_status"] != "asserted"
                or case["event_subtype"] in {"unknown", "ambiguous", "macro_announcement"}
            )
            and actual["assertion_status"] == "asserted"
            and actual["event_subtype"]
            in {"rate_hike", "rate_cut", "credit_deterioration", "supply_disruption"}
        )
        rows.append(
            {
                "id": case["id"],
                "text_sha256": hashlib.sha256(case["text"].encode()).hexdigest(),
                "url": case.get("url"),
                "slice": case.get("slice"),
                "expected": expected,
                "predicted": actual,
                "mismatches": mismatch,
                "unsafe_assertion": unsafe,
                "rule_ms": rule_ms,
                "sentiment_probabilities": sentiment.probabilities,
                "sentiment_score": sentiment.score,
                "tokens": sentiment.token_count,
                "chunks": sentiment.chunks,
                "truncated": sentiment.truncated,
            }
        )
    return {
        "class_metrics": classification_metrics(
            [row["expected"]["event_class"] for row in rows],
            [row["predicted"]["event_class"] for row in rows],
            [x.value for x in EventClass],
        ),
        "subtype_agreement": sum("event_subtype" not in row["mismatches"] for row in rows)
        / len(rows),
        "assertion_agreement": sum("assertion_status" not in row["mismatches"] for row in rows)
        / len(rows),
        "impact_exact_agreement": sum("impact_score" not in row["mismatches"] for row in rows)
        / len(rows),
        "impact_mae": sum(
            abs(row["expected"]["impact_score"] - row["predicted"]["impact_score"]) for row in rows
        )
        / len(rows),
        "unsafe_assertions": sum(row["unsafe_assertion"] for row in rows),
        "inference_timing": timing(times),
        "rule_timing": timing([row["rule_ms"] for row in rows]),
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--label", choices=["baseline", "refined"], required=True)
    parser.add_argument("--include-archive", action="store_true")
    args = parser.parse_args()
    report = {
        "started_at": utcnow().isoformat(),
        "label": args.label,
        "engine_version": ENGINE_VERSION,
        "model_revision": MODEL_REVISION,
        "model_sha256": MODEL_SHA256,
        "python": platform.python_version(),
        "code_sha256": {
            str(p.relative_to(ROOT)): sha(p)
            for p in [
                ROOT / "eventlens" / "classification.py",
                ROOT / "eventlens" / "sentiment.py",
                ROOT / "eventlens" / "evaluation.py",
                Path(__file__),
                ROOT / "requirements-dev.txt",
            ]
        },
        "candidate_label_review": "pending",
        "dataset_sha256": {},
        "limitations": [
            "PhraseBank may overlap model training",
            "AI-authored development labels",
            "Archived policy slice is narrow and template correlated",
            "No probability calibration or market-loss validation",
            "Serial local timings, not SLA",
        ],
    }
    model = FinBert(Settings().model_cache)
    started = time.perf_counter()
    model.load()
    if not model.ready:
        raise RuntimeError("Real pinned model unavailable; evaluation aborted")
    report["model_load_seconds"] = time.perf_counter() - started
    model.analyze("Warm-up example: the company's outlook remains unchanged.")
    phrase_path = ROOT / ".cache" / "evaluation" / "phrasebank-v1.json"
    frozen = json.loads(phrase_path.read_text(encoding="utf-8"))
    report["dataset_sha256"]["phrasebank"] = sha(phrase_path)
    rows, times = [], []
    for case in frozen["cases"]:
        started = time.perf_counter()
        result = model.analyze(case["text"])
        times.append((time.perf_counter() - started) * 1000)
        rows.append(
            {
                "id": case["id"],
                "expected": case["label"],
                "predicted": max(result.probabilities, key=result.probabilities.get),
                "probabilities": result.probabilities,
                "tokens": result.token_count,
                "chunks": result.chunks,
                "truncated": result.truncated,
            }
        )
    report["phrasebank"] = {
        "upstream_revision": frozen["revision"],
        "archive_sha256": frozen["archive_sha256"],
        "metrics": classification_metrics(
            [r["expected"] for r in rows], [r["predicted"] for r in rows], SENTIMENT_LABELS
        ),
        "inference_timing": timing(times),
        "rows": rows,
    }
    path = ROOT / "data" / "evaluation_development_v1.json"
    report["dataset_sha256"]["development"] = sha(path)
    report["development"] = events(json.loads(path.read_text(encoding="utf-8"))["cases"], model)
    if args.include_archive:
        path = ROOT / ".cache" / "evaluation" / "archive-policy-v1.json"
        archive = json.loads(path.read_text(encoding="utf-8"))
        manifest = ROOT / "data" / "evaluation_archive_v1.json"
        if archive["label_manifest_sha256"] != sha(manifest):
            raise ValueError("Archive labels changed after freezing")
        if any(
            hashlib.sha256(case["text"].encode()).hexdigest() != case["text_sha256"]
            for case in archive["cases"]
        ):
            raise ValueError("Frozen archive text changed")
        report["dataset_sha256"]["archive"] = sha(path)
        report["archive_coverage"] = {
            "requested": 12,
            "available": len(archive["cases"]),
            "failures": archive["failures"],
        }
        if archive["cases"]:
            report["archive"] = events(archive["cases"], model)
    report["finished_at"] = utcnow().isoformat()
    target = ROOT / "runtime" / f"phase5-evaluation-{args.label}-{uuid4().hex}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Report: {target}")
    print(
        json.dumps(
            {
                "phrasebank": report["phrasebank"]["metrics"],
                "development": {k: v for k, v in report["development"].items() if k != "rows"},
                "archive": {k: v for k, v in report.get("archive", {}).items() if k != "rows"},
                "archive_coverage": report.get("archive_coverage"),
                "development_mismatches": [
                    {"id": r["id"], "expected": r["expected"], "predicted": r["predicted"]}
                    for r in report["development"]["rows"]
                    if r["mismatches"]
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
