"""Core Google Photos functions using reverse-engineered batchexecute API.

All functions are usable without MCP server.
"""

import json
import os
import tempfile
import time
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_serializer

from mcp_handley_lab.common.config import settings

BATCHEXECUTE_URL = "https://photos.google.com/_/PhotosUi/data/batchexecute"
CONTENT_TYPE = "application/x-www-form-urlencoded;charset=utf-8"
MAX_PAGES = 5


# --- Response Models ---


class PhotoItem(BaseModel):
    """A photo item from Google Photos."""

    media_key: str = Field(..., description="Unique media key identifier.")
    url: str = Field(
        default="", description="Base URL (append =d for original quality)."
    )
    timestamp: int = Field(
        default=0, description="Unix timestamp (seconds) when taken."
    )
    width: int = Field(default=0, description="Image width in pixels.")
    height: int = Field(default=0, description="Image height in pixels.")


class PhotoDetail(BaseModel):
    """Detailed metadata for a single photo."""

    media_key: str = Field(..., description="Unique media key identifier.")
    download_url: str = Field(
        default="", description="Direct download URL for original quality."
    )
    filename: str = Field(default="", description="Original filename from the device.")
    width: int = Field(default=0, description="Image width in pixels.")
    height: int = Field(default=0, description="Image height in pixels.")
    timestamp: int = Field(
        default=0, description="Unix timestamp (seconds) when taken."
    )
    camera_make: str = Field(
        default="", description="Camera manufacturer (e.g., 'Nothing')."
    )
    camera_model: str = Field(default="", description="Camera model (e.g., 'A063').")
    size_bytes: int = Field(default=0, description="File size in bytes.")
    is_video: bool = Field(default=False, description="Whether this is a video.")


class DownloadResult(BaseModel):
    """Result of downloading photo(s)."""

    downloaded: list[str] = Field(
        default_factory=list, description="File paths successfully downloaded."
    )
    failed: list[str] = Field(
        default_factory=list, description="Media keys that failed to download."
    )
    output_dir: str = Field(
        default="", description="Directory where photos were saved."
    )


class GooglePhotosResult(BaseModel):
    """Envelope result — only relevant fields are populated."""

    model_config = ConfigDict(extra="forbid")

    photos: list[PhotoItem] | None = None
    detail: PhotoDetail | None = None
    download: DownloadResult | None = None

    @model_serializer
    def serialize(self) -> dict:
        """Exclude None fields from serialization."""
        return {k: v for k, v in self.__dict__.items() if v is not None}


# --- Session Management ---

_session_cache: tuple[httpx.Client, dict] | None = None


def _get_session(force_reload: bool = False) -> tuple[httpx.Client, dict]:
    """Load session from disk lazily, cached for process lifetime."""
    global _session_cache
    if _session_cache is not None and not force_reload:
        return _session_cache

    session_path = settings.google_photos_session_path
    data = json.loads(session_path.read_text())
    cookies = httpx.Cookies()
    for c in data.get("cookies", []):
        domain = c.get("domain") or ".google.com"
        cookies.set(c["name"], c["value"], domain=domain, path=c.get("path", "/"))

    client = httpx.Client(cookies=cookies, follow_redirects=True)
    wiz_data = data.get("wiz_data", {})
    _session_cache = (client, wiz_data)
    return _session_cache


def _clear_session_cache():
    """Clear cached session, closing the client."""
    global _session_cache
    if _session_cache is not None:
        client, _ = _session_cache
        client.close()
        _session_cache = None


# --- batchexecute helpers ---


def _build_request(wiz_data: dict, rpcid: str, args: list) -> tuple[str, str]:
    """Build batchexecute POST URL and body."""
    freq = json.dumps([[[rpcid, json.dumps(args), None, "generic"]]])
    url = (
        f"{BATCHEXECUTE_URL}?rpcids={rpcid}&source-path=/&"
        f"f.sid={wiz_data['f.sid']}&bl={wiz_data['bl']}&"
        f"hl=en&soc-app=165&soc-platform=1&soc-device=1&_reqid=100000&rt=c"
    )
    body = f"f.req={quote(freq)}&at={quote(wiz_data['at'])}&"
    return url, body


def _parse_response(resp: httpx.Response):
    """Parse batchexecute response: strip XSSI prefix, extract JSON payload.

    Detects HTML login redirects and raises RuntimeError.
    """
    content_type = resp.headers.get("content-type", "")
    if "text/html" in content_type:
        raise RuntimeError(
            "Session expired (redirected to login). Run gphotos-refresh-session."
        )

    text = resp.text
    if text.startswith(")]}'"):
        text = text[4:]
    text = text.strip()

    for line in text.split("\n"):
        line = line.strip()
        if line.startswith('[["wrb.fr"'):
            outer = json.loads(line)
            inner_str = outer[0][2]
            if inner_str is None:
                return None
            return json.loads(inner_str)
    return None


def _execute_rpc(client: httpx.Client, wiz_data: dict, rpcid: str, args: list):
    """Execute a batchexecute RPC call. Retries once on auth failure."""
    url, body = _build_request(wiz_data, rpcid, args)
    resp = client.post(url, content=body, headers={"Content-Type": CONTENT_TYPE})

    if resp.status_code in (400, 401, 403):
        _clear_session_cache()
        client, wiz_data = _get_session(force_reload=True)
        url, body = _build_request(wiz_data, rpcid, args)
        resp = client.post(url, content=body, headers={"Content-Type": CONTENT_TYPE})
        if resp.status_code in (400, 401, 403):
            raise RuntimeError(
                f"Google Photos auth failure (HTTP {resp.status_code}). "
                "Run gphotos-refresh-session."
            )

    resp.raise_for_status()

    try:
        return _parse_response(resp)
    except RuntimeError:
        _clear_session_cache()
        client, wiz_data = _get_session(force_reload=True)
        url, body = _build_request(wiz_data, rpcid, args)
        resp = client.post(url, content=body, headers={"Content-Type": CONTENT_TYPE})
        resp.raise_for_status()
        return _parse_response(resp)


def _parse_item(item: list) -> PhotoItem | None:
    """Parse a raw batchexecute item into a PhotoItem."""
    try:
        media_key = item[0]
        if not isinstance(media_key, str):
            return None
        info = item[1] if isinstance(item[1], list) else []
        url = info[0] if len(info) > 0 else ""
        width = info[1] if len(info) > 1 else 0
        height = info[2] if len(info) > 2 else 0
        timestamp = int(item[2]) // 1000 if isinstance(item[2], int | float) else 0
        return PhotoItem(
            media_key=media_key,
            url=url,
            timestamp=timestamp,
            width=width,
            height=height,
        )
    except (IndexError, TypeError):
        return None


# --- Public operations ---


def search_photos(query: str, limit: int = 50) -> list[PhotoItem]:
    """Search photos by text query via EzkLib RPC."""
    client, wiz_data = _get_session()
    data = _execute_rpc(client, wiz_data, "EzkLib", [query])

    if not data or not isinstance(data, list) or len(data) == 0:
        return []

    items = data[0] if isinstance(data[0], list) else data
    results = []
    for item in items:
        photo = _parse_item(item)
        if photo:
            results.append(photo)
        if len(results) >= limit:
            break

    return results


def list_recent_photos(
    days: int = 14,
    camera_make: str = "",
    camera_model: str = "",
    limit: int = 50,
) -> list[PhotoItem]:
    """List recent photos via lcxiM RPC with pagination."""
    client, wiz_data = _get_session()
    now_ms = int(time.time() * 1000)
    end_ts = now_ms
    start_ts = now_ms - (days * 24 * 60 * 60 * 1000)

    all_items: list[PhotoItem] = []
    need_camera_filter = bool(camera_make or camera_model)

    for _page in range(MAX_PAGES):
        data = _execute_rpc(
            client,
            wiz_data,
            "lcxiM",
            [None, end_ts, None, None, 1, 1, start_ts],
        )
        if not data or not isinstance(data, list) or len(data) == 0:
            break

        items = data[0] if isinstance(data[0], list) else data

        for raw_item in items:
            photo = _parse_item(raw_item)
            if not photo:
                continue

            if need_camera_filter:
                detail = _fetch_detail_raw(client, wiz_data, photo.media_key)
                if detail:
                    if camera_make and detail.get("camera_make") != camera_make:
                        continue
                    if camera_model and detail.get("camera_model") != camera_model:
                        continue

            all_items.append(photo)
            if len(all_items) >= limit:
                return all_items

        # Next page: use oldest timestamp
        timestamps = [
            i[2]
            for i in items
            if isinstance(i, list) and len(i) > 2 and isinstance(i[2], int | float)
        ]
        if timestamps:
            end_ts = min(timestamps) - 1
        else:
            break

    return all_items


def get_photo_detail(media_key: str) -> PhotoDetail:
    """Get full metadata for a photo via VrseUb + fDcn4b RPCs."""
    client, wiz_data = _get_session()
    detail = _fetch_detail_raw(client, wiz_data, media_key)
    if not detail:
        return PhotoDetail(media_key=media_key)

    filename = _fetch_filename(client, wiz_data, media_key)

    return PhotoDetail(
        media_key=media_key,
        download_url=detail.get("download_url", ""),
        filename=filename or "",
        width=detail.get("width", 0),
        height=detail.get("height", 0),
        timestamp=detail.get("timestamp", 0),
        camera_make=detail.get("camera_make", ""),
        camera_model=detail.get("camera_model", ""),
        size_bytes=detail.get("size_bytes", 0),
        is_video=detail.get("is_video", False),
    )


def download_photos(
    media_keys: list[str], output_dir: str = "/tmp/photos-live"
) -> DownloadResult:
    """Download photos by media key. Skips videos."""
    os.makedirs(output_dir, exist_ok=True)
    client, _ = _get_session()
    downloaded = []
    skipped = []

    for key in media_keys:
        detail = get_photo_detail(key)
        if not detail.download_url or detail.is_video:
            skipped.append(key)
            continue

        filename = detail.filename or f"{key[:20]}.jpg"
        ts_prefix = (
            time.strftime("%Y%m%d_%H%M%S", time.gmtime(detail.timestamp))
            if detail.timestamp
            else "unknown"
        )
        safe_name = f"{ts_prefix}_{key[:8]}_{filename}"
        output_path = os.path.join(output_dir, safe_name)

        resp = client.get(detail.download_url, follow_redirects=True)
        resp.raise_for_status()
        fd, tmp_path = tempfile.mkstemp(dir=output_dir, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(resp.content)
            os.rename(tmp_path, output_path)
        except Exception:
            os.unlink(tmp_path)
            raise
        downloaded.append(output_path)

    return DownloadResult(downloaded=downloaded, failed=skipped, output_dir=output_dir)


def show_photo(media_key: str) -> list:
    """Download photo and return as image content for visual display."""
    from mcp.server.fastmcp import Image
    from mcp.types import TextContent

    detail = get_photo_detail(media_key)
    if not detail.download_url:
        raise ValueError(f"No download URL for {media_key}")
    if detail.is_video:
        raise ValueError(f"{media_key} is a video, cannot show")

    client, _ = _get_session()
    resp = client.get(detail.download_url, follow_redirects=True)
    resp.raise_for_status()

    label = detail.filename or media_key[:20]
    meta = f"{label} ({detail.width}x{detail.height})"
    if detail.camera_make:
        meta += f" — {detail.camera_make} {detail.camera_model}"

    content_type = resp.headers.get("content-type", "image/jpeg")
    fmt = content_type.split("/")[-1].split(";")[0]
    if fmt not in {"jpeg", "png", "webp", "gif"}:
        fmt = "jpeg"

    return [
        TextContent(type="text", text=meta),
        Image(data=resp.content, format=fmt),
    ]


# --- Internal helpers ---


def _fetch_detail_raw(
    client: httpx.Client, wiz_data: dict, media_key: str
) -> dict | None:
    """Fetch photo metadata via VrseUb. Returns raw dict or None."""
    data = _execute_rpc(client, wiz_data, "VrseUb", [media_key, None, None, 1])
    if not data or not isinstance(data, list):
        return None

    info = data[0] if isinstance(data[0], list) else data

    try:
        image_info = info[1]
        base_url = image_info[0]
        width = image_info[1]
        height = image_info[2]
        timestamp_ms = info[2]

        extended = image_info[8] if len(image_info) > 8 else None

        camera_make = ""
        camera_model_val = ""
        if extended and isinstance(extended, list) and len(extended) > 4:
            exif = extended[4]
            if isinstance(exif, list) and len(exif) >= 2:
                camera_make = exif[0] or ""
                camera_model_val = exif[1] or ""

        size_bytes = 0
        if len(image_info) > 9 and isinstance(image_info[9], list):
            size_bytes = image_info[9][0] or 0

        # Video detection: extended[2] == 2 for videos
        is_video = (
            isinstance(extended, list) and len(extended) >= 3 and extended[2] == 2
        )

        return {
            "download_url": base_url + "=d",
            "width": width or 0,
            "height": height or 0,
            "timestamp": timestamp_ms // 1000 if timestamp_ms else 0,
            "camera_make": camera_make,
            "camera_model": camera_model_val,
            "size_bytes": size_bytes,
            "is_video": is_video,
        }
    except (IndexError, TypeError):
        return None


def _fetch_filename(client: httpx.Client, wiz_data: dict, media_key: str) -> str | None:
    """Fetch original filename via fDcn4b RPC."""
    data = _execute_rpc(client, wiz_data, "fDcn4b", [media_key])
    if data and isinstance(data, list) and len(data) > 0:
        inner = data[0] if isinstance(data[0], list) else data
        if isinstance(inner, list) and len(inner) > 2:
            return inner[2]
    return None
