from datetime import UTC, datetime

import httpx
import pytest

from eventlens.errors import DomainError
from eventlens.sources import FED_DID, Sources, canonical_release, parse_bluesky, parse_rss

NOW = datetime(2026, 10, 5, tzinfo=UTC)
RELEASE = "https://www.federalreserve.gov/newsevents/pressreleases/monetary20261002a.htm"
RSS = f"""<rss><channel><item><title>Federal Reserve issues FOMC statement</title>
<description>&lt;p&gt;Decision published.&lt;/p&gt;</description><link>{RELEASE}</link>
<pubDate>Fri, 02 Oct 2026 14:00:00 -0400</pubDate></item></channel></rss>""".encode()


@pytest.mark.parametrize(
    "url",
    [
        "http://www.federalreserve.gov/newsevents/pressreleases/monetary20261002a.htm",
        "https://www.federalreserve.gov.evil.test/newsevents/pressreleases/monetary20261002a.htm",
        "https://user@www.federalreserve.gov/newsevents/pressreleases/monetary20261002a.htm",
        "https://www.federalreserve.gov:444/newsevents/pressreleases/monetary20261002a.htm",
        "https://127.0.0.1/secret",
        "https://www.federalreserve.gov/../../private",
    ],
)
def test_release_allowlist_rejects_unsafe_urls(url):
    assert canonical_release(url) is None


def test_normalization_and_timezone():
    records = parse_rss(RSS, NOW, 5)
    record = records[0]
    assert record.published_at == datetime(2026, 10, 2, 18, tzinfo=UTC)
    assert "<p>" not in record.text
    assert record.verified_publisher
    assert record.linked_release_url == RELEASE
    assert parse_rss(RSS, NOW, 5)[0].id == record.id


def test_xml_entities_are_not_resolved():
    payload = b'<!DOCTYPE x [<!ENTITY a SYSTEM "file:///secret">]><rss>&a;</rss>'
    with pytest.raises(DomainError, match="parse"):
        parse_rss(payload, NOW, 5)


def social_feed(did=FED_DID, text="Official statement published."):
    return {
        "feed": [
            {
                "post": {
                    "uri": f"at://{did}/app.bsky.feed.post/example1",
                    "author": {"did": did},
                    "record": {
                        "text": text,
                        "createdAt": "2026-10-02T18:01:00Z",
                        "facets": [{"features": [{"uri": RELEASE}]}],
                    },
                }
            }
        ]
    }


def test_social_preserves_channel_and_linked_release():
    record = parse_bluesky(social_feed(), NOW, 5)[0]
    assert record.source_family == "social"
    assert record.linked_release_url == RELEASE
    assert record.publisher == parse_rss(RSS, NOW, 5)[0].publisher


def test_nonofficial_author_is_not_ingested_as_official():
    assert parse_bluesky(social_feed("did:plc:fake"), NOW, 5) == []


def test_redirect_is_not_followed():
    seen = []

    def respond(request):
        seen.append(str(request.url))
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(DomainError) as error:
            Sources(client=client).fetch("fed_rss", NOW)
    assert error.value.code == "SOURCE_HTTP_ERROR"
    assert len(seen) == 1


def test_rss_expands_generic_title_only_from_allowlisted_release():
    def respond(request):
        if str(request.url).endswith("press_all.xml"):
            return httpx.Response(200, content=RSS)
        assert str(request.url) == RELEASE
        return httpx.Response(
            200,
            text='<div id="article"><p>The FOMC decided to lower the target range by 50 basis points.</p></div>',
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        record = Sources(client=client).fetch("fed_rss", NOW)[0]
    assert record.text_kind == "full_release"
    assert "50 basis points" in record.text


def test_large_source_response_is_bounded():
    with httpx.Client(
        transport=httpx.MockTransport(lambda r: httpx.Response(200, content=b"x" * 2_000_001))
    ) as client:
        with pytest.raises(DomainError) as error:
            Sources(client=client).fetch("fed_rss", NOW)
    assert error.value.code == "SOURCE_TOO_LARGE"


def test_source_429_preserves_retry_after_without_retry_loop():
    seen = []

    def respond(request):
        seen.append(request)
        return httpx.Response(429, headers={"retry-after": "600"})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(DomainError) as error:
            Sources(client=client).fetch("fed_rss", NOW)
    assert error.value.retry_after == 600
    assert len(seen) == 1
