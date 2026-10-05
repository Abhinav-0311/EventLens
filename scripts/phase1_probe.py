"""Check Phase 1 feasibility; this is not the application or an accuracy benchmark."""

import argparse
import json
import math
import os
import platform
import statistics
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("HF_HOME", str(ROOT / ".cache" / "huggingface"))
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "60")

USER_AGENT = "EventLens-Feasibility/0.1 (read-only academic prototype)"
URLS = {
    "federal_reserve_rss": "https://www.federalreserve.gov/feeds/press_all.xml",
    "bls_cpi_release_rss": "https://www.bls.gov/feed/cpi.rss",
    "bluesky_official_author": (
        "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed"
        "?actor=federalreserve.gov&limit=5"
    ),
    "finbert_manifest": "https://huggingface.co/api/models/ProsusAI/finbert",
}


def request_bytes(url: str, maximum: int = 2_000_000) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        body = response.read(maximum + 1)
        if len(body) > maximum:
            raise ValueError("Response exceeds probe size limit")
        return response.status, body


def source_probe() -> dict:
    results = {}
    for name, url in URLS.items():
        start = time.perf_counter()
        try:
            status, body = request_bytes(url)
            result = {"status": status}
            if name.endswith("_rss"):
                root = ET.fromstring(body)
                items = root.findall("./channel/item")
                atom = "{http://www.w3.org/2005/Atom}"
                entries = root.findall(f"{atom}entry")
                first_url = items[0].findtext("link") if items else None
                if entries:
                    link = entries[0].find(f"{atom}link")
                    first_url = link.get("href") if link is not None else None
                result.update(
                    record_count=len(items) or len(entries),
                    first_record_url=first_url,
                    feed_format="atom" if entries else "rss",
                    parsed_text_fields=["title", "summary" if entries else "description"],
                )
            elif name == "bluesky_official_author":
                feed = json.loads(body).get("feed", [])
                posts = [item.get("post", {}) for item in feed]
                result.update(
                    record_count=len(posts),
                    nonempty_text_count=sum(
                        bool(post.get("record", {}).get("text", "").strip()) for post in posts
                    ),
                    publisher="Federal Reserve Board official account",
                    independent_of_rss_publisher=False,
                )
            else:
                manifest = json.loads(body)
                result.update(
                    model_id=manifest.get("id"),
                    revision=manifest.get("sha"),
                    pipeline_tag=manifest.get("pipeline_tag"),
                    files=[item["rfilename"] for item in manifest.get("siblings", [])],
                    declared_model_card_license=manifest.get("cardData", {}).get("license"),
                )
            result["elapsed_seconds"] = round(time.perf_counter() - start, 3)
            results[name] = result
        except (urllib.error.URLError, ValueError, ET.ParseError) as error:
            results[name] = {
                "error": str(error),
                "elapsed_seconds": round(time.perf_counter() - start, 3),
            }
    return results


def api_probe() -> dict:
    import asyncio
    from decimal import Decimal

    import fastapi
    import httpx
    import pydantic
    import uvicorn
    from pydantic import BaseModel

    class Amount(BaseModel):
        amount: Decimal

    app = fastapi.FastAPI()

    @app.post("/_phase1/amount", response_model=Amount)
    def amount(body: Amount) -> Amount:
        return body

    async def exercise() -> tuple:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://phase1.local"
        ) as client:
            response = await client.post("/_phase1/amount", json={"amount": "10.25"})
            invalid = await client.post("/_phase1/amount", json={"amount": "not-a-number"})
            return response, invalid

    response, invalid = asyncio.run(exercise())
    return {
        "fastapi_version": fastapi.__version__,
        "pydantic_version": pydantic.__version__,
        "httpx_version": httpx.__version__,
        "uvicorn_version": uvicorn.__version__,
        "decimal_roundtrip_passed": response.status_code == 200
        and response.json() == {"amount": "10.25"},
        "validation_error_passed": invalid.status_code == 422,
        "purpose": "In-process library compatibility check, not a running EventLens API.",
    }


def model_probe(revision: str, offline: bool) -> dict:
    import torch
    import transformers
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    torch.set_num_threads(4)
    start = time.perf_counter()
    options = {
        "revision": revision,
        "token": False,
        "trust_remote_code": False,
        "local_files_only": offline,
    }
    tokenizer = AutoTokenizer.from_pretrained("ProsusAI/finbert", **options)
    model = AutoModelForSequenceClassification.from_pretrained(
        "ProsusAI/finbert", use_safetensors=False, **options
    )
    model.eval()
    load_seconds = time.perf_counter() - start
    examples = [
        ("positive", "The company reported strong profit growth and increased its dividend."),
        ("negative", "The company defaulted on its debt and reported substantial losses."),
        ("neutral", "The company will publish its quarterly report on Tuesday."),
    ]
    outputs = []
    with torch.inference_mode():
        for expected, text in examples:
            inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512)
            start = time.perf_counter()
            probabilities = torch.softmax(model(**inputs).logits, dim=-1)[0]
            seconds = time.perf_counter() - start
            scores = {
                model.config.id2label[index].lower(): float(value)
                for index, value in enumerate(probabilities)
            }
            score = scores["positive"] - scores["negative"]
            outputs.append(
                {
                    "text": text,
                    "expected_smoke_label": expected,
                    "label": max(scores, key=scores.get),
                    "probabilities": {key: round(value, 6) for key, value in scores.items()},
                    "sentiment_score": round(score, 6),
                    "inference_seconds": round(seconds, 3),
                    "probabilities_sum_to_one": math.isclose(
                        sum(scores.values()), 1.0, abs_tol=1e-6
                    ),
                    "score_in_range": -1 <= score <= 1,
                }
            )
        # Warm timings separate tokenizer and forward pass from network/model load.
        warm = []
        for _ in range(5):
            start = time.perf_counter()
            inputs = tokenizer(examples[1][1], return_tensors="pt", truncation=True, max_length=512)
            model(**inputs)
            warm.append(time.perf_counter() - start)
    return {
        "model_id": "ProsusAI/finbert",
        "revision": revision,
        "offline": offline,
        "device": "cpu",
        "torch_version": torch.__version__,
        "transformers_version": transformers.__version__,
        "load_seconds": round(load_seconds, 3),
        "warm_single_text_median_seconds": round(statistics.median(warm), 3),
        "max_sequence_tokens": model.config.max_position_embeddings,
        "examples": outputs,
        "purpose": "Functional smoke check on three synthetic examples; not an accuracy benchmark.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", action="store_true")
    parser.add_argument("--revision")
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--api", action="store_true")
    args = parser.parse_args()
    if args.model and not args.revision:
        parser.error("--model requires a pinned --revision")
    if args.offline and not (args.model or args.api):
        parser.error("--offline requires --model or --api")
    report = {
        "checked_at": datetime.now(UTC).isoformat(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
    }
    if not args.offline:
        report["sources"] = source_probe()
    if args.model:
        report["model"] = model_probe(args.revision, args.offline)
    if args.api:
        report["api_runtime"] = api_probe()
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
