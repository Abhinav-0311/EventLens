import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from eventlens.config import Settings
from eventlens.schemas import Sentiment
from eventlens.sources import make_record

NOW = datetime(2026, 10, 5, tzinfo=UTC)
RELEASE = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261002a.htm"


class FakeModel:
    """Explicit test double, never an application fallback."""

    ready = True
    error_code = None

    def load(self):
        pass

    def analyze(self, text):
        return Sentiment(
            score=0.3,
            probabilities={"positive": 0.5, "negative": 0.2, "neutral": 0.3},
            model_id="test-double",
            model_revision="test",
            inference_mode="test_only",
            token_count=len(text.split()),
            chunks=1,
        )


class FakeSources:
    def fetch(self, source_id, now):
        return [
            make_record(
                source_id=source_id,
                family="official_release" if source_id == "fed_rss" else "social",
                uri=RELEASE if source_id == "fed_rss" else "at://test/post/1",
                linked=RELEASE,
                text="The Federal Reserve raised its policy rate by 50 basis points.",
                kind="full_release" if source_id == "fed_rss" else "post",
                published=now,
                retrieved=now,
            )
        ]

    def close(self):
        pass


@pytest.fixture
def settings(tmp_path):
    return Settings(database_path=tmp_path / "test.sqlite3", refresh_interval_seconds=300)


def run_api(app, scenario):
    async def exercise():
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app), base_url="http://localhost"
            ) as client:
                return await scenario(client)

    return asyncio.run(exercise())


async def await_operation(client, operation_id):
    for _ in range(200):
        result = (await client.get(f"/api/operations/{operation_id}")).json()
        if result["status"] not in {"queued", "running"}:
            return result
        await asyncio.sleep(0.01)
    raise AssertionError("Operation did not finish within the test deadline")
