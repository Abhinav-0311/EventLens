"""Freeze bounded diagnostic inputs before prediction; raw corpus stays ignored."""

import argparse
import hashlib
import io
import json
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import requests
from bs4 import BeautifulSoup
from huggingface_hub import hf_hub_download

from eventlens.config import ROOT
from eventlens.evaluation import select_balanced
from eventlens.schemas import utcnow
from eventlens.sources import plain_text

REVISION = "8d3fe0c36d5feec6b3cc5e455b0fcb4820fb9964"
CACHE = ROOT / ".cache" / "evaluation"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save_once(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(f"Frozen: {path.name}; SHA256={sha(path.read_bytes())}")


def phrasebank():
    target = CACHE / "phrasebank-v1.json"
    if target.exists():
        print(f"Already frozen: {target.name}; SHA256={sha(target.read_bytes())}")
        return
    downloaded = hf_hub_download(
        "takala/financial_phrasebank",
        "data/FinancialPhraseBank-v1.0.zip",
        repo_type="dataset",
        revision=REVISION,
        token=False,
        cache_dir=CACHE / "downloads",
    )
    raw = Path(downloaded).read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        names = [name for name in archive.namelist() if name.endswith("Sentences_AllAgree.txt")]
        if len(names) != 1 or archive.getinfo(names[0]).file_size > 2_000_000:
            raise ValueError("Unexpected all-agreement archive member")
        sentences = archive.read(names[0]).decode("latin-1")
    rows = [line.rsplit("@", 1) for line in sentences.splitlines() if line.strip()]
    if len(rows) != 2264:
        raise ValueError("Unexpected upstream row count")
    save_once(
        target,
        {
            "version": "phrasebank-diagnostic-v1",
            "frozen_at": utcnow().isoformat(),
            "source": "takala/financial_phrasebank",
            "revision": REVISION,
            "license": "CC-BY-NC-SA-3.0",
            "archive_sha256": sha(raw),
            "upstream_rows": len(rows),
            "selection": "lowest sentence SHA256, 30 per class",
            "limitation": "Possible FinBERT training overlap; not independent accuracy",
            "cases": select_balanced(rows),
        },
    )


def policy_archive():
    target = CACHE / "archive-policy-v1.json"
    if target.exists():
        print(f"Already frozen: {target.name}; SHA256={sha(target.read_bytes())}")
        return
    manifest_path = ROOT / "data" / "evaluation_archive_v1.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    records, failures = [], []
    for source in manifest["sources"]:
        expected = (
            "https://www.federalreserve.gov/newsevents/pressreleases/monetary"
            + source["date"].replace("-", "")
            + "a.htm"
        )
        if source["url"] != expected:
            raise ValueError("Archive URL does not match the fixed official source")
        try:
            with requests.get(
                expected, timeout=(10, 30), allow_redirects=False, stream=True
            ) as response:
                response.raise_for_status()
                if response.status_code != 200:
                    raise ValueError("Redirects are not followed")
                raw = bytearray()
                for chunk in response.iter_content(65536):
                    raw.extend(chunk)
                    if len(raw) > 2_000_000:
                        raise ValueError("Archive body exceeds bound")
                soup = BeautifulSoup(bytes(raw), "html.parser")
            article = soup.select_one("#article")
            if article is None:
                raise ValueError("Official article container missing")
            text = " ".join(plain_text(str(p)) for p in article.select("p"))
            if not 100 <= len(text) <= 12000:
                raise ValueError("Article length outside application contract")
            records.append(
                source
                | {
                    "text": text,
                    "text_sha256": sha(text.encode()),
                    "page_sha256": sha(raw),
                    "retrieved_at": utcnow().isoformat(),
                    "text_kind": "full_release",
                    "provenance_mode": "archive_evaluation",
                }
            )
            print(f"Frozen archive source {source['id']}", flush=True)
        except (requests.RequestException, ValueError) as error:
            failures.append({"id": source["id"], "url": expected, "error": type(error).__name__})
            print(f"Archive source {source['id']} unavailable: {type(error).__name__}", flush=True)
    save_once(
        target,
        manifest
        | {
            "frozen_at": utcnow().isoformat(),
            "label_manifest_sha256": sha(manifest_path.read_bytes()),
            "cases": records,
            "failures": failures,
        },
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--archive", action="store_true", help="Also freeze 12 fixed official releases"
    )
    args = parser.parse_args()
    phrasebank()
    if args.archive:
        policy_archive()
