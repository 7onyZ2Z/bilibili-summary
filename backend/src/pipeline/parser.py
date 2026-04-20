from __future__ import annotations

import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

from src.models import VideoMetadata


BVID_PATTERN = re.compile(r"BV[0-9A-Za-z]{10}")
AVID_PATTERN = re.compile(r"(?:av|aid=)(\d+)", flags=re.IGNORECASE)
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}

# Module-level session for connection pooling
_bilibili_session = requests.Session()
_bilibili_session.headers.update(DEFAULT_HEADERS)


class ParseError(RuntimeError):
    pass


def resolve_url(url: str, timeout_seconds: int) -> str:
    candidate = url.strip()
    if not candidate:
        raise ParseError("Input URL is empty.")

    if not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"

    parsed = urlparse(candidate)
    host = parsed.netloc.lower()

    # For canonical bilibili video links, avoid fetching webpage directly.
    # Direct page requests may return 412 and are unnecessary for BV/AV extraction.
    if host.endswith("bilibili.com") and parsed.path.lower().startswith("/video/"):
        return candidate

    # b23.tv often redirects to canonical bilibili links.
    if host in {"b23.tv", "www.b23.tv"}:
        response = _bilibili_session.get(
            candidate,
            timeout=timeout_seconds,
            allow_redirects=True,
        )
        response.raise_for_status()
        return response.url

    return candidate


def _extract_bvid(url: str) -> str | None:
    match = BVID_PATTERN.search(url)
    return match.group(0) if match else None


def _extract_avid(url: str) -> str | None:
    match = AVID_PATTERN.search(url)
    return match.group(1) if match else None


def fetch_video_metadata(url: str, timeout_seconds: int) -> VideoMetadata:
    resolved_url = resolve_url(url, timeout_seconds)
    bvid = _extract_bvid(resolved_url)
    avid = _extract_avid(resolved_url)

    params = None
    video_id = None
    if bvid:
        params = {"bvid": bvid}
        video_id = bvid
        source_url = f"https://www.bilibili.com/video/{bvid}"
    elif avid:
        params = {"aid": avid}
        video_id = f"av{avid}"
        source_url = f"https://www.bilibili.com/video/{video_id}"
    else:
        raise ParseError("Could not extract BV/AV id from URL.")

    response = _bilibili_session.get(
        "https://api.bilibili.com/x/web-interface/view",
        params=params,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    payload = response.json()

    code = payload.get("code", -1)
    if code != 0:
        raise ParseError(f"Bilibili API error: code={code}, message={payload.get('message', '')}")

    data = payload.get("data", {})
    title = data.get("title", "untitled_video")
    owner_name = data.get("owner", {}).get("name", "unknown_uploader")

    pubdate = data.get("pubdate")
    publish_time = datetime.fromtimestamp(pubdate, tz=timezone.utc) if isinstance(pubdate, int) else None

    return VideoMetadata(
        video_id=video_id,
        title=title,
        owner_name=owner_name,
        publish_time=publish_time,
        source_url=source_url,
    )
