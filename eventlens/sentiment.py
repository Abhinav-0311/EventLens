import hashlib
import logging
import threading
from pathlib import Path

from eventlens.config import MODEL_ID, MODEL_REVISION, MODEL_SHA256
from eventlens.errors import DomainError
from eventlens.schemas import Sentiment

logger = logging.getLogger(__name__)


def aggregate_probabilities(rows: list[list[float]], weights: list[int]) -> list[float]:
    if not rows or len(rows) != len(weights) or sum(weights) <= 0:
        raise ValueError("Nonempty predictions and positive token weights are required")
    return [
        sum(row[i] * weight for row, weight in zip(rows, weights, strict=True)) / sum(weights)
        for i in range(3)
    ]


class FinBert:
    def __init__(self, cache: Path):
        self.cache = cache
        self.ready = False
        self.error_code = "MODEL_UNAVAILABLE"
        self._lock = threading.Lock()

    def load(self):
        """Offline only. Never silently download or substitute a lexical model."""
        try:
            snapshot = self.cache / "models--ProsusAI--finbert" / "snapshots" / MODEL_REVISION
            weights = snapshot / "pytorch_model.bin"
            if not weights.is_file() or weights.stat().st_size != 437_992_753:
                raise ValueError("Pinned cached weights unavailable")
            checksum = hashlib.sha256()
            with weights.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    checksum.update(chunk)
            if checksum.hexdigest() != MODEL_SHA256:
                raise ValueError("Pinned weight checksum mismatch")
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            torch.set_num_threads(4)
            options = {"local_files_only": True, "trust_remote_code": False}
            self.tokenizer = AutoTokenizer.from_pretrained(str(snapshot), **options)
            self.model = AutoModelForSequenceClassification.from_pretrained(
                str(snapshot), use_safetensors=False, **options
            )
            self.model.eval()
            self.ready, self.error_code = True, None
        except Exception:
            self.ready, self.error_code = False, "MODEL_UNAVAILABLE"
            logger.warning(
                "Pinned local FinBERT unavailable; use scripts/download_model.py then restart."
            )

    def analyze(self, text: str) -> Sentiment:
        if not self.ready:
            raise DomainError(
                "MODEL_UNAVAILABLE",
                "Pinned local model is unavailable; no prediction was generated.",
            )
        import torch

        try:
            with self._lock, torch.inference_mode():
                tokens = self.tokenizer.encode(text, add_special_tokens=False)
                if not tokens:
                    raise DomainError("EMPTY_TOKENS", "Text contains no analyzable tokens.", 422)
                chunks = [tokens[i : i + 510] for i in range(0, min(len(tokens), 8160), 510)]
                rows = []
                for chunk in chunks:
                    ids = torch.tensor([self.tokenizer.build_inputs_with_special_tokens(chunk)])
                    probabilities = torch.softmax(
                        self.model(input_ids=ids, attention_mask=torch.ones_like(ids)).logits,
                        dim=-1,
                    )[0]
                    rows.append([float(p) for p in probabilities])
                combined = aggregate_probabilities(rows, [len(chunk) for chunk in chunks])
                labels = {self.model.config.id2label[i].lower(): p for i, p in enumerate(combined)}
                return Sentiment(
                    score=labels["positive"] - labels["negative"],
                    probabilities=labels,
                    model_id=MODEL_ID,
                    model_revision=MODEL_REVISION,
                    token_count=len(tokens),
                    chunks=len(chunks),
                    truncated=len(tokens) > 8160,
                )
        except DomainError:
            raise
        except Exception as error:
            raise DomainError(
                "MODEL_INFERENCE_FAILED",
                "Local sentiment inference failed; no prediction was substituted.",
            ) from error
