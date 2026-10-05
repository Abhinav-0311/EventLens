import hashlib
import re
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup
from defusedxml import ElementTree

from eventlens.errors import DomainError
from eventlens.schemas import SourceRecord, digest

FED_DID = "did:plc:d3vmaxc5ytftnf4gwdwptupg"
PUBLISHER = "Federal Reserve Board"
SOURCE_IDS = ("fed_rss", "fed_bluesky")
URLS = {
    "fed_rss": "https://www.federalreserve.gov/feeds/press_all.xml",
    "fed_bluesky": "https://public.api.bsky.app/xrpc/app.bsky.feed.getAuthorFeed?actor=federalreserve.gov&limit=20",
}


def canonical_release(url: str) -> str | None:
    try:
        parts = urlsplit(url)
        if (
            parts.scheme != "https"
            or parts.hostname != "www.federalreserve.gov"
            or parts.username
            or parts.password
            or parts.port not in (None, 443)
            or not re.fullmatch(r"/newsevents/pressreleases/[a-z]+\d{8}[a-z]?\.htm", parts.path)
        ):
            return None
        return urlunsplit(("https", "www.federalreserve.gov", parts.path, "", ""))
    except ValueError:
        return None


def plain_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style"]):
        element.decompose()
    return re.sub(r"\s+", " ", soup.get_text(" ", strip=True)).strip()


def make_record(
    *,
    source_id: str,
    family: str,
    uri: str,
    text: str,
    kind: str,
    published: datetime,
    retrieved: datetime,
    linked: str | None = None,
    flags: list[str] | None = None,
) -> SourceRecord:
    if published.tzinfo is None:
        raise ValueError("Publisher timestamp has no timezone")
    input_flags = list(flags or [])
    if len(text) > 12000:
        text = text[:12000]
        input_flags.append("source_text_truncated")
    content_hash = hashlib.sha256(text.encode()).hexdigest()
    return SourceRecord(
        id=digest(source_id, PUBLISHER, uri, content_hash),
        source_id=source_id,
        source_family=family,
        publisher=PUBLISHER,
        canonical_uri=uri,
        linked_release_url=linked,
        text=text,
        text_kind=kind,
        published_at=published,
        retrieved_at=retrieved,
        provenance_mode="live",
        content_hash=content_hash,
        verified_publisher=True,
        input_flags=input_flags,
    )


def parse_rss(body: bytes, now: datetime, limit: int) -> list[SourceRecord]:
    try:
        root = ElementTree.fromstring(body)
        records = []
        for item in root.findall("./channel/item")[:limit]:
            uri = canonical_release(item.findtext("link", ""))
            if not uri:
                continue
            title = plain_text(item.findtext("title", ""))
            description = plain_text(item.findtext("description", ""))
            text = f"{title}. {description}".strip()
            if not title and not description:
                continue
            records.append(
                make_record(
                    source_id="fed_rss",
                    family="official_release",
                    uri=uri,
                    linked=uri,
                    text=text,
                    kind="headline_summary",
                    published=parsedate_to_datetime(item.findtext("pubDate", "")),
                    retrieved=now,
                )
            )
        return records
    except Exception as error:
        raise DomainError(
            "SOURCE_PARSE_ERROR", "Cannot parse the official RSS response."
        ) from error


def parse_bluesky(body: dict, now: datetime, limit: int) -> list[SourceRecord]:
    try:
        records = []
        for item in body.get("feed", [])[:limit]:
            post = item.get("post", {})
            uri = post.get("uri", "")
            record = post.get("record", {})
            if post.get("author", {}).get("did") != FED_DID or not re.fullmatch(
                re.escape(f"at://{FED_DID}/app.bsky.feed.post/") + r"[a-zA-Z0-9]+", uri
            ):
                continue
            text = record.get("text", "").strip()
            if not text or (record.get("langs") and "en" not in record["langs"]):
                continue
            linked = None
            for facet in record.get("facets", []):
                for feature in facet.get("features", []):
                    candidate = canonical_release(feature.get("uri", ""))
                    if candidate:
                        linked = candidate
                        break
            records.append(
                make_record(
                    source_id="fed_bluesky",
                    family="social",
                    uri=uri,
                    text=text,
                    kind="post",
                    published=datetime.fromisoformat(record["createdAt"].replace("Z", "+00:00")),
                    retrieved=now,
                    linked=linked,
                )
            )
        return records
    except Exception as error:
        raise DomainError(
            "SOURCE_PARSE_ERROR", "Cannot parse the official social response."
        ) from error


class Sources:
    def __init__(self, limit: int = 5, client: httpx.Client | None = None, sleeper=time.sleep):
        self.limit = limit
        self.client = client or httpx.Client(
            timeout=25,
            follow_redirects=False,
            headers={"User-Agent": "EventLens/0.2 (academic public-data prototype)"},
        )
        self._owned_client = client is None
        self.sleeper = sleeper

    def close(self):
        if self._owned_client:
            self.client.close()

    def _get(self, url: str) -> bytes:
        # Only fixed endpoints or validated official release pages can be fetched.
        if url not in URLS.values() and canonical_release(url) != url:
            raise DomainError("SOURCE_URL_REJECTED", "Source URL is not allowlisted.")
        for attempt in range(2):
            try:
                with self.client.stream("GET", url, follow_redirects=False, timeout=25) as response:
                    if response.status_code == 429:
                        retry = response.headers.get("retry-after", "300")
                        if retry.isdigit():
                            seconds = max(1, min(int(retry), 86400))
                        else:
                            try:
                                seconds = max(
                                    1,
                                    min(
                                        int(
                                            (
                                                parsedate_to_datetime(retry) - datetime.now(UTC)
                                            ).total_seconds()
                                        ),
                                        86400,
                                    ),
                                )
                            except (ValueError, TypeError):
                                seconds = 300
                        raise DomainError(
                            "SOURCE_RATE_LIMITED",
                            "Publisher rate limit; retry later.",
                            retry_after=seconds,
                        )
                    if response.status_code >= 500 and attempt == 0:
                        self.sleeper(1)
                        continue
                    if response.status_code != 200:
                        raise DomainError(
                            "SOURCE_HTTP_ERROR",
                            "Publisher response unavailable; no redirects followed.",
                        )
                    body = bytearray()
                    for chunk in response.iter_bytes(chunk_size=65536):
                        body.extend(chunk)
                        if len(body) > 2_000_000:
                            raise DomainError(
                                "SOURCE_TOO_LARGE", "Publisher response exceeds the size limit."
                            )
                    return bytes(body)
            except httpx.HTTPError as error:
                if attempt == 0:
                    self.sleeper(1)
                    continue
                raise DomainError(
                    "SOURCE_NETWORK_ERROR", "Publisher could not be reached."
                ) from error
        raise DomainError("SOURCE_NETWORK_ERROR", "Publisher could not be reached.")

    def fetch(self, source_id: str, now: datetime) -> list[SourceRecord]:
        if source_id not in URLS:
            raise DomainError("SOURCE_UNKNOWN", "Unknown configured source.", 404)
        body = self._get(URLS[source_id])
        if source_id == "fed_bluesky":
            import json

            try:
                records = parse_bluesky(json.loads(body), now, self.limit)
            except (ValueError, TypeError) as error:
                raise DomainError("SOURCE_PARSE_ERROR", "Invalid social response.") from error
        else:
            records = parse_rss(body, now, self.limit)
            expanded = []
            for record in records:
                if re.search(r"\b(?:FOMC statement|monetary policy)\b", record.text, re.I):
                    try:
                        soup = BeautifulSoup(self._get(record.canonical_uri), "html.parser")
                        article = soup.select_one("#article")
                        paragraphs = article.select("p") if article else []
                        text = " ".join(plain_text(str(p)) for p in paragraphs)
                        if not text:
                            raise DomainError(
                                "SOURCE_PARSE_ERROR", "Official release text not found."
                            )
                        record = make_record(
                            source_id="fed_rss",
                            family="official_release",
                            uri=record.canonical_uri,
                            linked=record.linked_release_url,
                            text=text,
                            kind="full_release",
                            published=record.published_at,
                            retrieved=now,
                        )
                    except DomainError:
                        # Keep the real retrieved summary but explicitly block assumptions from missing detail.
                        record.input_flags.append("release_expansion_failed")
                expanded.append(record)
            records = expanded
        if not records:
            raise DomainError("SOURCE_EMPTY", "Source returned no valid English text records.")
        return records
