import pytest
from pydantic import ValidationError

from eventlens.errors import DomainError
from eventlens.schemas import AnalyzeRequest, Sentiment
from eventlens.sentiment import FinBert, aggregate_probabilities


def test_token_weighted_chunk_aggregation():
    probabilities = aggregate_probabilities([[0.8, 0.1, 0.1], [0.2, 0.6, 0.2]], [3, 1])
    assert probabilities == pytest.approx([0.65, 0.225, 0.125])


@pytest.mark.parametrize("text", ["", "   ", "abc\x00def", "x" * 12001])
def test_bad_supplied_text_is_rejected(text):
    with pytest.raises(ValidationError):
        AnalyzeRequest(text=text)


def test_user_cannot_claim_verified_provenance():
    with pytest.raises(ValidationError):
        AnalyzeRequest(text="Some text", verified_publisher=True)


def test_probability_and_score_validation():
    with pytest.raises(ValidationError):
        Sentiment(
            score=0.9,
            probabilities={"positive": 0.5, "negative": 0.2, "neutral": 0.3},
            model_id="test",
            model_revision="test",
            token_count=1,
            chunks=1,
        )


def test_uncached_model_stays_unavailable(tmp_path):
    model = FinBert(tmp_path)
    model.load()
    assert not model.ready
    assert model.error_code == "MODEL_UNAVAILABLE"
    with pytest.raises(DomainError):
        model.analyze("Some text")


@pytest.mark.model
def test_real_model_and_chunking():
    from eventlens.config import Settings

    model = FinBert(Settings().model_cache)
    model.load()
    assert model.ready
    positive = model.analyze(
        "The company reported strong profit growth and increased its dividend."
    )
    negative = model.analyze("The company defaulted on its debt and reported substantial losses.")
    assert positive.score > 0
    assert negative.score < 0
    long_text = model.analyze("The company reported strong profit growth. " * 100)
    assert long_text.chunks > 1
    assert not long_text.truncated


@pytest.mark.model
def test_inference_empty_tokens_truncation_and_failure(tmp_path):
    from types import SimpleNamespace

    import torch

    class TokenizerDouble:
        count = 8170

        def encode(self, text, add_special_tokens):
            return [1] * self.count

        def build_inputs_with_special_tokens(self, tokens):
            return [2, *tokens, 3]

    class ForwardDouble:
        config = SimpleNamespace(id2label={0: "positive", 1: "negative", 2: "neutral"})
        fail = False

        def __call__(self, input_ids, attention_mask):
            assert input_ids.shape[1] <= 512
            if self.fail:
                raise RuntimeError("Simulated inference failure")
            return SimpleNamespace(logits=torch.tensor([[0.0, 2.0, 0.0]]))

    model = FinBert(tmp_path)
    model.ready = True
    model.tokenizer, model.model = TokenizerDouble(), ForwardDouble()
    result = model.analyze("controlled test input")
    assert result.truncated and result.chunks == 16 and result.token_count == 8170
    model.tokenizer.count = 0
    with pytest.raises(DomainError) as error:
        model.analyze("controlled test input")
    assert error.value.code == "EMPTY_TOKENS"
    model.tokenizer.count = 1
    model.model.fail = True
    with pytest.raises(DomainError) as error:
        model.analyze("controlled test input")
    assert error.value.code == "MODEL_INFERENCE_FAILED"
