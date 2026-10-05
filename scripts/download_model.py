"""Explicit one-time acquisition; server startup itself is always offline."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from huggingface_hub import snapshot_download

from eventlens.config import MODEL_ID, MODEL_REVISION, Settings
from eventlens.sentiment import FinBert


def main():
    settings = Settings()
    snapshot_download(
        MODEL_ID,
        revision=MODEL_REVISION,
        cache_dir=settings.model_cache,
        token=False,
        allow_patterns=[
            "config.json",
            "tokenizer_config.json",
            "special_tokens_map.json",
            "vocab.txt",
            "pytorch_model.bin",
        ],
        max_workers=1,
    )
    model = FinBert(settings.model_cache)
    model.load()
    if not model.ready:
        raise RuntimeError(
            "Downloaded model did not pass pinned-weight verification and local loading"
        )
    print(f"Verified {MODEL_ID} at {MODEL_REVISION}. Ready for offline startup.")


if __name__ == "__main__":
    main()
