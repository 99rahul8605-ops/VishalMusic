import asyncio
import contextlib
import json
import os
import sys
import glob
import re
import time
import aiohttp
import shutil
from typing import Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from py_yt import VideosSearch

from VISHALMUSIC.utils.cookie_handler import COOKIE_PATH
from VISHALMUSIC.utils.database import is_on_off
from VISHALMUSIC.utils.downloader import download_audio_concurrent, yt_dlp_download
from VISHALMUSIC.utils.errors import capture_internal_err
from VISHALMUSIC.utils.formatters import time_to_seconds
from VISHALMUSIC.utils.tuning import (
    YTDLP_TIMEOUT,
    YOUTUBE_META_MAX,
    YOUTUBE_META_TTL,
)
from VISHALMUSIC import LOGGER

_cache: Dict[str, Tuple[float, List[Dict]]] = {}
_cache_lock = asyncio.Lock()
_formats_cache: Dict[str, Tuple[float, List[Dict], str]] = {}
_formats_lock = asyncio.Lock()

# ============ API CONFIGURATION ============
# Custom fast API from .env
FAST_API_URL = os.getenv("API_URL", "").strip().rstrip("/")
FAST_API_KEY = os.getenv("API_KEY", "")
AUDIO_DIRECT_STREAM_MB = float(os.getenv("AUDIO_DIRECT_STREAM_MB", "20"))
AUDIO_DIRECT_STREAM_BYTES = int(AUDIO_DIRECT_STREAM_MB * 1024 * 1024)
AUDIO_DOWNLOAD_WORKERS = max(1, min(int(os.getenv("AUDIO_DOWNLOAD_WORKERS", "3")), 12))
AUDIO_DOWNLOAD_RETRIES = max(1, min(int(os.getenv("AUDIO_DOWNLOAD_RETRIES", "3")), 5))
_audio_fast_locks = {}

# Existing Shruti API remains as fallback
SHRUTI_API_KEY = "ShrutiBotspCO4qB3gMS2eDCpMeClO"
PRIMARY_API_URL = "https://api.shrutibots.site"

# API 2: Legacy/Fallback API (Token Based)
FALLBACK_API_URL = ""
# Endpoint 1: /download?url={video_id}&type=audio -> returns {"download_token": "xxx"}
# Endpoint 2: /stream/{video_id}?type=audio with header X-Download-Token

# API URLs loaded status
PRIMARY_API_LOADED = False
FALLBACK_API_LOADED = False

# ============ RATE LIMITING ============
_request_timestamps = []
_RATE_LIMIT_WINDOW = 60
_MAX_REQUESTS_PER_WINDOW = 10

async def load_apis():
    """Load and verify both APIs"""
    global PRIMARY_API_LOADED, FALLBACK_API_LOADED
    logger = LOGGER("VISHALMUSIC.platforms.Youtube.py")

    if FAST_API_URL:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{FAST_API_URL}/",
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        logger.info(f"✅ FAST API loaded successfully: {FAST_API_URL}")
                    else:
                        logger.warning(f"⚠️ Fast API responded with status {response.status}")
        except Exception as e:
            logger.warning(f"⚠️ Fast API not accessible: {e}")
    else:
        logger.warning("⚠️ API_URL is not set; Fast API disabled.")
    
    # Check Primary API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{PRIMARY_API_URL}/", timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    PRIMARY_API_LOADED = True
                    logger.info(f"✅ PRIMARY API URL loaded successfully: {PRIMARY_API_URL}")
                else:
                    logger.warning(f"⚠️ Primary API responded with status {response.status}")
    except Exception as e:
        logger.warning(f"⚠️ Primary API not accessible: {str(e)}")
    
    # Check Fallback API
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{FALLBACK_API_URL}/", timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    FALLBACK_API_LOADED = True
                    logger.info(f"✅ FALLBACK API URL loaded successfully: {FALLBACK_API_URL}")
                else:
                    logger.warning(f"⚠️ Fallback API responded with status {response.status}")
    except Exception as e:
        logger.warning(f"⚠️ Fallback API not accessible: {str(e)}")
    
    return PRIMARY_API_LOADED, FALLBACK_API_LOADED

# Initialize APIs on startup
try:
    loop = asyncio.get_event_loop()
    if loop.is_running():
        asyncio.create_task(load_apis())
    else:
        loop.run_until_complete(load_apis())
except RuntimeError:
    pass

def _cookiefile_path() -> Optional[str]:
    path = str(COOKIE_PATH)
    try:
        if path and os.path.exists(path) and os.path.getsize(path) > 0:
            return path
    except Exception:
        pass
    return None

def _cookies_args() -> List[str]:
    p = _cookiefile_path()
    return ["--cookies", p] if p else []

async def _exec_proc(*args: str) -> Tuple[bytes, bytes]:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        return await asyncio.wait_for(proc.communicate(), timeout=YTDLP_TIMEOUT)
    except asyncio.TimeoutError:
        with contextlib.suppress(Exception):
            proc.kill()
        return b"", b"timeout"

def _check_rate_limit():
    global _request_timestamps
    now = time.time()
    _request_timestamps = [ts for ts in _request_timestamps if now - ts < _RATE_LIMIT_WINDOW]
    if len(_request_timestamps) >= _MAX_REQUESTS_PER_WINDOW:
        sleep_time = _RATE_LIMIT_WINDOW - (now - _request_timestamps[0])
        time.sleep(sleep_time)
        _request_timestamps = []
    _request_timestamps.append(now)

# ============ CUSTOM FAST API DIRECT STREAM ============
async def get_fast_audio_stream(link: str) -> Optional[str]:
    """Return the signed direct audio URL without downloading the media locally."""
    if not FAST_API_URL:
        return None

    try:
        print(f"⚡ Audio - Getting direct stream from Fast API: {FAST_API_URL}")
        timeout = aiohttp.ClientTimeout(total=30)
        params = {"api_key": FAST_API_KEY} if FAST_API_KEY else {}

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{FAST_API_URL}/song/{video_id}",
                params=params,
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    print(f"⚠️ Fast API returned {response.status}: {body[:250]}")
                    return None

                data = await response.json(content_type=None)

        if data.get("status") != "done":
            print(f"⚠️ Fast API extraction failed: {data.get('message', 'unknown error')}")
            return None

        stream_url = data.get("link")
        stream_format = str(data.get("format") or "").lower().strip()

        # Direct HTTP playback is very fast, but WebM/Opus streams have been
        # intermittently entering a "playing but silent" state in Telegram VC.
        # Keep the fast path only for M4A/MP4 audio. Other containers fall back
        # to the local Fast-API download path below, which is slower to start
        # but much more reliable.
        direct_safe_formats = {"m4a", "mp4"}
        if (
            stream_url
            and stream_url.startswith("http")
            and stream_format in direct_safe_formats
        ):
            print(f"✅ Fast API direct audio stream ready ({stream_format})")
            return stream_url

        if stream_url and stream_url.startswith("http"):
            print(
                f"⚠️ Fast API direct format '{stream_format or 'unknown'}' "
                "is not VC-safe; using reliable local fallback"
            )
        else:
            print("⚠️ Fast API returned no valid stream URL")

        return None
    except Exception as e:
        print(f"❌ Fast API stream error: {e}")
        return None


# ============ CUSTOM FAST API (PRIMARY AUDIO) ============

def _get_audio_fast_lock(video_id: str) -> asyncio.Lock:
    lock = _audio_fast_locks.get(video_id)
    if lock is None:
        lock = asyncio.Lock()
        _audio_fast_locks[video_id] = lock
    return lock


async def _remote_media_size(session: aiohttp.ClientSession, url: str) -> int:
    """
    Get a reliable total size without downloading the file.

    Range probing is preferred over HEAD because YouTube/CDN signed URLs can
    report misleading Content-Length values on HEAD.
    """
    base_headers = {
        "Accept": "*/*",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    }

    range_headers = dict(base_headers)
    range_headers["Range"] = "bytes=0-0"

    try:
        async with session.get(
            url,
            headers=range_headers,
            allow_redirects=True,
        ) as r:
            content_range = r.headers.get("Content-Range", "")
            if r.status == 206 and "/" in content_range:
                total = content_range.rsplit("/", 1)[-1].strip()
                if total.isdigit():
                    return int(total)

            value = r.headers.get("Content-Length")
            if r.status == 200 and value and value.isdigit():
                return int(value)
    except Exception:
        pass

    try:
        async with session.head(
            url,
            headers=base_headers,
            allow_redirects=True,
        ) as r:
            if r.status < 400:
                value = r.headers.get("Content-Length")
                if value and value.isdigit():
                    return int(value)
    except Exception:
        pass

    return 0


async def _download_media_parallel(
    session: aiohttp.ClientSession,
    url: str,
    total_size: int,
    temp_path: str,
) -> bool:
    """
    Download a known-size media file with parallel byte ranges.

    YouTube media hosts usually support HTTP ranges. Multiple concurrent
    ranges avoid the very slow single-connection throttling that can make a
    5 MB track take minutes.
    """
    if total_size <= 0:
        return False

    workers = min(AUDIO_DOWNLOAD_WORKERS, max(1, total_size // (512 * 1024)))
    workers = max(1, workers)

    # A single worker offers no advantage over the normal fallback path.
    if workers <= 1:
        return False

    chunk_size = (total_size + workers - 1) // workers
    part_paths = [f"{temp_path}.p{i}" for i in range(workers)]

    async def fetch_part(i: int):
        start = i * chunk_size
        end = min(total_size - 1, start + chunk_size - 1)
        expected = end - start + 1

        last_error = None

        for attempt in range(1, AUDIO_DOWNLOAD_RETRIES + 1):
            headers = {
                "Accept": "*/*",
                "Accept-Encoding": "identity",
                "Connection": "keep-alive",
                "Range": f"bytes={start}-{end}",
            }

            try:
                async with session.get(
                    url,
                    headers=headers,
                    allow_redirects=True,
                ) as r:
                    if r.status != 206:
                        raise RuntimeError(
                            f"range {i} returned HTTP {r.status}, expected 206"
                        )

                    written = 0
                    with open(part_paths[i], "wb", buffering=1024 * 1024) as f:
                        async for chunk in r.content.iter_chunked(512 * 1024):
                            if not chunk:
                                continue
                            f.write(chunk)
                            written += len(chunk)

                    if written == expected:
                        return

                    raise RuntimeError(
                        f"range {i} incomplete: {written}/{expected} bytes"
                    )

            except (
                aiohttp.ClientPayloadError,
                aiohttp.ServerDisconnectedError,
                ConnectionResetError,
                asyncio.TimeoutError,
                RuntimeError,
            ) as e:
                last_error = e
                with contextlib.suppress(Exception):
                    if os.path.exists(part_paths[i]):
                        os.remove(part_paths[i])

                if attempt < AUDIO_DOWNLOAD_RETRIES:
                    await asyncio.sleep(0.25 * attempt)
                    continue

        raise RuntimeError(
            f"range {i} failed after {AUDIO_DOWNLOAD_RETRIES} tries: {last_error}"
        )

    try:
        await asyncio.gather(*(fetch_part(i) for i in range(workers)))

        with open(temp_path, "wb", buffering=1024 * 1024) as out:
            for part in part_paths:
                with open(part, "rb") as inp:
                    shutil.copyfileobj(inp, out, length=1024 * 1024)

        final_size = os.path.getsize(temp_path)
        if final_size != total_size:
            raise RuntimeError(
                f"combined range file incomplete: {final_size}/{total_size}"
            )

        return True

    except Exception as e:
        print(f"⚠️ Parallel range download failed: {type(e).__name__}: {e}")
        with contextlib.suppress(Exception):
            if os.path.exists(temp_path):
                os.remove(temp_path)
        return False

    finally:
        for part in part_paths:
            with contextlib.suppress(Exception):
                if os.path.exists(part):
                    os.remove(part)


async def _download_media_resumable(
    session: aiohttp.ClientSession,
    url: str,
    temp_path: str,
    expected_size: int = 0,
):
    """
    Single-stream fallback with resume.

    If the CDN/VPS connection resets after e.g. 3,129,328 of 3,178,465 bytes,
    keep the bytes already received and request only the missing tail instead
    of abandoning Fast API immediately.
    """
    last_error = None
    expected = int(expected_size or 0)

    for attempt in range(1, AUDIO_DOWNLOAD_RETRIES + 1):
        offset = 0
        if os.path.exists(temp_path):
            with contextlib.suppress(Exception):
                offset = os.path.getsize(temp_path)

        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "identity",
            "Connection": "keep-alive",
        }
        if offset > 0:
            headers["Range"] = f"bytes={offset}-"

        try:
            async with session.get(
                url,
                headers=headers,
                allow_redirects=True,
            ) as media:
                if media.status == 403:
                    return False, 403, expected

                if media.status not in (200, 206):
                    return False, media.status, expected

                # If server ignored Range and returned a full 200 response,
                # restart the temp file instead of appending duplicate bytes.
                if offset > 0 and media.status == 200:
                    offset = 0
                    with contextlib.suppress(Exception):
                        os.remove(temp_path)

                content_range = media.headers.get("Content-Range", "")
                if "/" in content_range:
                    total = content_range.rsplit("/", 1)[-1].strip()
                    if total.isdigit():
                        expected = int(total)
                elif not expected and media.content_length:
                    expected = int(media.content_length) + offset

                mode = "ab" if offset > 0 and media.status == 206 else "wb"
                with open(temp_path, mode, buffering=1024 * 1024) as f:
                    async for chunk in media.content.iter_chunked(1024 * 1024):
                        if not chunk:
                            continue
                        f.write(chunk)

            current = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0

            if expected:
                if current >= expected:
                    return True, 200, expected
                last_error = RuntimeError(
                    f"incomplete payload: {current}/{expected} bytes"
                )
            elif current > 10240:
                return True, 200, current

        except (
            aiohttp.ClientPayloadError,
            aiohttp.ServerDisconnectedError,
            ConnectionResetError,
            asyncio.TimeoutError,
        ) as e:
            last_error = e

        current = os.path.getsize(temp_path) if os.path.exists(temp_path) else 0
        if attempt < AUDIO_DOWNLOAD_RETRIES:
            if current:
                print(
                    f"↻ Media connection interrupted at "
                    f"{current / (1024 * 1024):.2f} MB; "
                    f"resuming ({attempt + 1}/{AUDIO_DOWNLOAD_RETRIES})..."
                )
            else:
                print(
                    f"↻ Media connection interrupted; retrying "
                    f"({attempt + 1}/{AUDIO_DOWNLOAD_RETRIES})..."
                )
            await asyncio.sleep(0.35 * attempt)

    print(
        "⚠️ Media download incomplete after retries: "
        f"{type(last_error).__name__ if last_error else 'unknown'}: {last_error}"
    )
    return False, 0, expected


async def download_song_fast_api(link: str) -> Optional[str]:
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if "youtu.be/" in video_id:
        video_id = video_id.split("youtu.be/")[-1].split("?")[0]
    video_id = video_id.strip()

    if not video_id or len(video_id) < 3:
        return None

    # The same track can reach download() twice during queue/autoplay races.
    # Serialize by video id so we do not download the same 5 MB file twice.
    lock = _get_audio_fast_lock(video_id)
    async with lock:
        return await _download_song_fast_api_locked(link, video_id)


async def _download_song_fast_api_locked(link: str, video_id: str) -> Optional[str]:
    """
    Direct-stream Fast API mode.

    Fast API extracts the signed media URL and we return it immediately to
    PyTgCalls/FFmpeg. No local audio download, size probe, or parallel ranges.
    """
    if not FAST_API_URL:
        return None

    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if "youtu.be/" in video_id:
        video_id = video_id.split("youtu.be/")[-1].split("?")[0]
    video_id = video_id.strip()

    if not video_id or len(video_id) < 3:
        return None

    try:
        print(f"⚡ Audio - Fast API direct stream mode: {FAST_API_URL}")

        params = {"api_key": FAST_API_KEY} if FAST_API_KEY else {}

        timeout = aiohttp.ClientTimeout(
            total=25,
            connect=8,
            sock_connect=8,
            sock_read=18,
        )

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(
                f"{FAST_API_URL}/song/{video_id}",
                params=params,
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    print(
                        f"⚠️ Fast API returned {response.status}: "
                        f"{body[:250]}"
                    )
                    return None

                data = await response.json(content_type=None)

        if data.get("status") != "done":
            print(
                "⚠️ Fast API extraction failed: "
                f"{data.get('message', 'unknown error')}"
            )
            return None

        stream_url = data.get("link")
        if not stream_url or not str(stream_url).startswith(("http://", "https://")):
            print("⚠️ Fast API returned no valid audio stream URL")
            return None

        print("🚀 Audio direct stream ready")
        return str(stream_url)

    except asyncio.TimeoutError:
        print("❌ Fast API direct stream timeout")
        return None
    except Exception as e:
        print(
            f"❌ Fast API direct stream error: "
            f"{type(e).__name__}: {e!r}"
        )
        return None


async def download_song_primary_api(link: str) -> str:
    """Primary Shruti API - Direct download with API key"""
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link

    if not video_id or len(video_id) < 3:
        return None

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    try:
        print(f"🔄 Trying Primary API (Direct): {PRIMARY_API_URL}")

        async with aiohttp.ClientSession() as session:
            params = {"url": video_id, "type": "audio", "api_key": SHRUTI_API_KEY}
            
            async with session.get(
                f"{PRIMARY_API_URL}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=120)
            ) as response:
                if response.status != 200:
                    print(f"⚠️ Primary API returned status {response.status}")
                    return None

                with open(file_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(131072):
                        f.write(chunk)
                
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    print(f"✅ Audio downloaded via Primary API")
                    return file_path
                return None

    except Exception as e:
        print(f"❌ Primary API error: {str(e)}")
        return None


async def download_video_primary_api(link: str) -> str:
    """Primary Shruti API - Video download with API key"""
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link

    if not video_id or len(video_id) < 3:
        return None

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    try:
        print(f"🔄 Trying Primary API (Direct): {PRIMARY_API_URL}")

        async with aiohttp.ClientSession() as session:
            params = {"url": video_id, "type": "video", "api_key": SHRUTI_API_KEY}
            
            async with session.get(
                f"{PRIMARY_API_URL}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=180)
            ) as response:
                if response.status != 200:
                    print(f"⚠️ Primary API returned status {response.status}")
                    return None

                with open(file_path, "wb") as f:
                    async for chunk in response.content.iter_chunked(131072):
                        f.write(chunk)
                
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    print(f"✅ Video downloaded via Primary API")
                    return file_path
                return None

    except Exception as e:
        print(f"❌ Primary API error: {str(e)}")
        return None


# ============ API 2: LEGACY/FALLBACK API (TOKEN BASED) ============
async def download_song_fallback_api(link: str) -> str:
    """Legacy/Fallback API - Token based download"""
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link

    if not video_id or len(video_id) < 3:
        return None

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp3")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    try:
        print(f"🔄 Trying Fallback API (Token): {FALLBACK_API_URL}")

        async with aiohttp.ClientSession() as session:
            # Step 1: Get download token
            params = {"url": video_id, "type": "audio"}
            
            async with session.get(
                f"{FALLBACK_API_URL}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    print(f"⚠️ Fallback API returned status {response.status}")
                    return None

                data = await response.json()
                download_token = data.get("download_token")
                
                if not download_token:
                    print("⚠️ No download token received from Fallback API")
                    return None
            
            # Step 2: Download using token
            stream_url = f"{FALLBACK_API_URL}/stream/{video_id}?type=audio"
            
            async with session.get(
                stream_url,
                headers={"X-Download-Token": download_token},
                timeout=aiohttp.ClientTimeout(total=300)
            ) as file_response:
                if file_response.status != 200:
                    print(f"⚠️ Fallback stream returned status {file_response.status}")
                    return None
                
                with open(file_path, "wb") as f:
                    async for chunk in file_response.content.iter_chunked(16384):
                        f.write(chunk)
                
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    print(f"✅ Audio downloaded via Fallback API")
                    return file_path
                return None

    except Exception as e:
        print(f"❌ Fallback API error: {str(e)}")
        return None


async def download_video_fallback_api(link: str) -> str:
    """Legacy/Fallback API - Video download with token"""
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link

    if not video_id or len(video_id) < 3:
        return None

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
        return file_path

    try:
        print(f"🔄 Trying Fallback API (Token): {FALLBACK_API_URL}")

        async with aiohttp.ClientSession() as session:
            # Step 1: Get download token
            params = {"url": video_id, "type": "video"}
            
            async with session.get(
                f"{FALLBACK_API_URL}/download",
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status != 200:
                    print(f"⚠️ Fallback API returned status {response.status}")
                    return None

                data = await response.json()
                download_token = data.get("download_token")
                
                if not download_token:
                    print("⚠️ No download token received from Fallback API")
                    return None
            
            # Step 2: Download using token
            stream_url = f"{FALLBACK_API_URL}/stream/{video_id}?type=video"
            
            async with session.get(
                stream_url,
                headers={"X-Download-Token": download_token},
                timeout=aiohttp.ClientTimeout(total=600)
            ) as file_response:
                if file_response.status != 200:
                    print(f"⚠️ Fallback stream returned status {file_response.status}")
                    return None
                
                with open(file_path, "wb") as f:
                    async for chunk in file_response.content.iter_chunked(16384):
                        f.write(chunk)
                
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    print(f"✅ Video downloaded via Fallback API")
                    return file_path
                return None

    except Exception as e:
        print(f"❌ Fallback API error: {str(e)}")
        return None



def _find_cached_audio(video_id: str) -> Optional[str]:
    """Find a real downloaded audio file without changing its extension."""
    for ext in ("m4a", "webm", "opus", "ogg", "mp3", "mp4"):
        p = os.path.join("downloads", f"{video_id}.{ext}")
        try:
            if os.path.exists(p) and os.path.getsize(p) > 10240:
                return p
        except Exception:
            pass

    for p in glob.glob(os.path.join("downloads", f"{video_id}.*")):
        if p.endswith(".part"):
            continue
        try:
            if os.path.isfile(p) and os.path.getsize(p) > 10240:
                return p
        except Exception:
            pass
    return None


def _yt_dlp_runtime_args() -> List[str]:
    """Use Deno + EJS for current YouTube JS challenge handling."""
    args = []

    deno_path = shutil.which("deno")
    if not deno_path and os.path.exists("/root/.deno/bin/deno"):
        deno_path = "/root/.deno/bin/deno"

    if deno_path:
        args += ["--js-runtimes", f"deno:{deno_path}"]
    else:
        print("⚠️ Deno not found; yt-dlp JS challenge solving may fail")

    args += ["--remote-components", "ejs:npm"]
    return args


# ============ YT-DLP FALLBACK ============
async def download_video_ytdlp(link: str) -> str:
    """Download video using yt-dlp directly"""
    video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link

    if not video_id or len(video_id) < 3:
        return None

    DOWNLOAD_DIR = "downloads"
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    file_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.mp4")

    if os.path.exists(file_path) and os.path.getsize(file_path) > 10240:
        return file_path

    _check_rate_limit()
    
    try:
        ytdlp_opts = [
            "yt-dlp",
            *(_cookies_args()),
            "--no-warnings",
            "--geo-bypass",
            "--force-ipv4",
            "-f",
            "best[height<=?720][width<=?1280]/best",
            "-o",
            file_path,
            link
        ]
        
        stdout, stderr = await _exec_proc(*ytdlp_opts)
        
        if os.path.exists(file_path) and os.path.getsize(file_path) > 10240:
            return file_path
        else:
            alternative_formats = ["best[ext=mp4]", "best", "worst[ext=mp4]", "worst"]
            
            for fmt in alternative_formats:
                try:
                    ytdlp_opts = [
                        "yt-dlp",
                        *(_cookies_args()),
                        "--no-warnings",
                        "--geo-bypass",
                        "--force-ipv4",
                        "-f",
                        fmt,
                        "-o",
                        file_path,
                        link
                    ]
                    
                    stdout, stderr = await _exec_proc(*ytdlp_opts)
                    
                    if os.path.exists(file_path) and os.path.getsize(file_path) > 10240:
                        return file_path
                    
                    await asyncio.sleep(1)
                except Exception:
                    continue
            
            return None

    except Exception as e:
        return None


async def download_audio_ytdlp(link: str) -> str:
    """
    Robust local yt-dlp fallback:
    - Deno + EJS
    - native audio container, no transcode
    - preserves real extension
    """
    video_id = link.split("v=")[-1].split("&")[0] if "v=" in link else link
    if "youtu.be/" in video_id:
        video_id = video_id.split("youtu.be/")[-1].split("?")[0]
    video_id = video_id.strip()

    if not video_id or len(video_id) < 3:
        return None

    os.makedirs("downloads", exist_ok=True)

    cached = _find_cached_audio(video_id)
    if cached:
        print(f"✅ yt-dlp local cache: {cached}")
        return cached

    _check_rate_limit()

    output_template = os.path.join("downloads", f"{video_id}.%(ext)s")
    formats = [
        "bestaudio[ext=m4a]/bestaudio[ext=webm]/bestaudio/best",
        "bestaudio/best",
    ]

    for idx, fmt in enumerate(formats, start=1):
        try:
            cmd = [
                sys.executable, "-m", "yt_dlp",
                *(_cookies_args()),
                *(_yt_dlp_runtime_args()),
                "--no-playlist",
                "--no-warnings",
                "--geo-bypass",
                "--force-ipv4",
                "--retries", "3",
                "--fragment-retries", "3",
                "--socket-timeout", "20",
                "-f", fmt,
                "-o", output_template,
                link,
            ]

            print(f"🔄 yt-dlp local fallback attempt {idx}/{len(formats)}")
            stdout, stderr = await _exec_proc(*cmd)

            cached = _find_cached_audio(video_id)
            if cached:
                print(f"✅ yt-dlp local audio ready: {cached}")
                return cached

            err = stderr.decode("utf-8", "ignore").strip()
            if err:
                print(f"⚠️ yt-dlp attempt {idx} failed: {err[-700:]}")

        except Exception as e:
            print(f"⚠️ yt-dlp attempt {idx} exception: {e}")

    return None


# ============ MAIN DOWNLOAD FUNCTIONS (API1 -> API2 -> YTDLP) ============
async def download_audio(link: str) -> str:
    """
    Main audio download - Fast API -> Shruti API -> Legacy API -> yt-dlp
    """
    # 1. TRY CUSTOM FAST API FIRST
    result = await download_song_fast_api(link)
    if result:
        print("✅ Audio: Fast API Success")
        return result

    # 2. TRY EXISTING SHRUTI API
    print("🔄 Audio - Fast API failed, trying Shruti API...")
    result = await download_song_primary_api(link)
    if result:
        print("✅ Audio: Shruti API Success")
        return result

    # 3. TRY LEGACY/TOKEN API
    print("🔄 Audio - Shruti failed, trying Legacy API...")
    result = await download_song_fallback_api(link)
    if result:
        print("✅ Audio: Legacy API Success")
        return result

    # 4. TRY LOCAL YT-DLP AS LAST RESORT
    print("🔄 Audio - APIs failed, trying yt-dlp fallback...")
    result = await download_audio_ytdlp(link)
    if result:
        print("✅ Audio: yt-dlp Success")
        # Keep the real container/extension. Renaming bytes without
        # transcoding can confuse FFmpeg/PyTgCalls.
        return result
    
    print("❌ All audio download methods failed")
    return None


async def download_video(link: str) -> str:
    """
    Main video download - Primary API -> Fallback API -> yt-dlp
    """
    # 1. TRY PRIMARY API FIRST
    print("🎬 Video Download - Trying Primary API (Direct)...")
    result = await download_video_primary_api(link)
    if result:
        print("✅ Video: Primary API Success")
        return result
    
    # 2. TRY FALLBACK API (TOKEN BASED)
    print("🔄 Video - Primary failed, trying Fallback API (Token)...")
    result = await download_video_fallback_api(link)
    if result:
        print("✅ Video: Fallback API Success")
        return result
    
    # 3. TRY YT-DLP AS LAST RESORT
    print("🔄 Video - Both APIs failed, trying yt-dlp fallback...")
    result = await download_video_ytdlp(link)
    if result:
        print("✅ Video: yt-dlp Success")
        return result
    
    print("❌ All video download methods failed")
    return None


# ============ YOUTUBE API CLASS ============
@capture_internal_err
async def cached_youtube_search(query: str) -> List[Dict]:
    key = f"q:{query}"
    now = time.time()

    async with _cache_lock:
        if key in _cache:
            ts, val = _cache[key]
            if now - ts < YOUTUBE_META_TTL:
                return val
            _cache.pop(key, None)
        if len(_cache) > YOUTUBE_META_MAX:
            _cache.clear()

    result: List[Dict] = []

    # 1) Fast API search by song name
    if FAST_API_URL:
        try:
            params = {
                "q": query,
                "limit": 1,
            }
            if FAST_API_KEY:
                params["api_key"] = FAST_API_KEY

            async with aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=20)
            ) as session:
                async with session.get(
                    f"{FAST_API_URL}/search",
                    params=params,
                ) as response:
                    if response.status == 200:
                        data = await response.json(content_type=None)
                        api_results = data.get("results", [])

                        for item in api_results:
                            video_id = item.get("id") or item.get("video_id") or ""
                            title = item.get("title", "")
                            duration = item.get("duration")
                            thumbnail = item.get("thumbnail") or ""
                            channel = item.get("channel") or item.get("uploader") or ""

                            # Normalize to the structure expected by the existing bot
                            result.append({
                                "id": video_id,
                                "title": title,
                                "duration": duration,
                                "thumbnail": thumbnail,
                                "thumbnails": [{"url": thumbnail}] if thumbnail else [],
                                "channel": channel,
                                "webpage_url": (
                                    f"https://www.youtube.com/watch?v={video_id}"
                                    if video_id else ""
                                ),
                            })

                        if result:
                            print(f"✅ Search via Fast API: {query}")
                    else:
                        print(f"⚠️ Fast API search returned status {response.status}")
        except Exception as e:
            print(f"⚠️ Fast API search failed: {e}")

    # 2) Existing py_yt search as fallback
    if not result:
        try:
            data = await VideosSearch(query, limit=1).next()
            result = data.get("result", [])
            if result:
                print(f"✅ Search via py_yt fallback: {query}")
        except Exception:
            result = []

    if result:
        async with _cache_lock:
            _cache[key] = (now, result)

    return result

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")

class YouTubeAPI:
    def __init__(self) -> None:
        self.base_url = "https://www.youtube.com/watch?v="
        self.playlist_url = "https://youtube.com/playlist?list="
        self.status = "https://www.youtube.com/oembed?url="
        self._url_pattern = re.compile(r"(?:youtube\.com|youtu\.be)")
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    def _prepare_link(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        if isinstance(videoid, str) and videoid.strip():
            link = self.base_url + videoid.strip()
        if "youtu.be" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        elif "youtube.com/shorts/" in link or "youtube.com/live/" in link:
            link = self.base_url + link.split("/")[-1].split("?")[0]
        return link.split("&")[0]

    @capture_internal_err
    async def url(self, message: Message) -> Optional[str]:
        msgs = [message] + ([message.reply_to_message] if message.reply_to_message else [])
        for msg in msgs:
            text = msg.text or msg.caption or ""
            entities = msg.entities or msg.caption_entities or []
            for ent in entities:
                if ent.type == MessageEntityType.URL:
                    url = text[ent.offset : ent.offset + ent.length]
                    if self._url_pattern.search(url):
                        return url
                if ent.type == MessageEntityType.TEXT_LINK:
                    url = ent.url
                    if self._url_pattern.search(url):
                        return url
        return None

    @capture_internal_err
    async def exists(self, link: str, videoid: Union[str, bool, None] = None) -> bool:
        return bool(self._url_pattern.search(self._prepare_link(link, videoid)))

    @capture_internal_err
    async def _fetch_video_info(self, query: str, *, use_cache: bool = True) -> Optional[Dict]:
        q = self._prepare_link(query)
        if use_cache and not q.startswith("http"):
            res = await cached_youtube_search(q)
            return res[0] if res else None
        data = await VideosSearch(q, limit=1).next()
        result = data.get("result", [])
        return result[0] if result else None

    @capture_internal_err
    async def is_live(self, link: str) -> bool:
        _check_rate_limit()
        prepared = self._prepare_link(link)
        stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
        if not stdout:
            return False
        try:
            info = json.loads(stdout.decode())
            return bool(info.get("is_live"))
        except json.JSONDecodeError:
            return False

    @capture_internal_err
    async def details(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], int, str, str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if not info:
            raise ValueError("Video not found")
        dt = info.get("duration")
        ds = int(time_to_seconds(dt)) if dt else 0
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        return info.get("title", ""), dt, ds, thumb, info.get("id", "")

    @capture_internal_err
    async def title(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("title", "") if info else ""

    @capture_internal_err
    async def duration(self, link: str, videoid: Union[str, bool, None] = None) -> Optional[str]:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        return info.get("duration") if info else None

    @capture_internal_err
    async def thumbnail(self, link: str, videoid: Union[str, bool, None] = None) -> str:
        info = await self._fetch_video_info(self._prepare_link(link, videoid))
        if info:
            thumb = info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")
            return thumb.split("?")[0] if thumb else ""
        return ""

    @capture_internal_err
    async def video(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[int, str]:
        link = self._prepare_link(link, videoid)
        
        try:
            downloaded_file = await download_video(link)
            if downloaded_file:
                return (1, downloaded_file)
        except Exception:
            pass
        
        _check_rate_limit()
        
        ytdlp_args = [
            "yt-dlp", *(_cookies_args()), "--no-warnings", "--geo-bypass", "--force-ipv4",
            "-g", "-f", "best[height<=?720][width<=?1280]/best", link
        ]
        
        stdout, stderr = await _exec_proc(*ytdlp_args)
        
        if stdout:
            stream_url = stdout.decode().split("\n")[0]
            if stream_url and stream_url.startswith('http'):
                return (1, stream_url)
            else:
                return (0, "Invalid stream URL")
        else:
            error_msg = stderr.decode() if stderr else "Unknown error"
            if "429" in error_msg or "Too Many Requests" in error_msg:
                await asyncio.sleep(30)
                return (0, "Rate limited")
            elif "403" in error_msg:
                return await self._try_alternative_format(link)
            else:
                return (0, error_msg)

    async def _try_alternative_format(self, link: str) -> Tuple[int, str]:
        format_options = ["best[height<=480]", "best[ext=mp4]", "best", "worst"]
        for fmt in format_options:
            stdout, stderr = await _exec_proc("yt-dlp", *(_cookies_args()), "--no-warnings", "-g", "-f", fmt, link)
            if stdout:
                stream_url = stdout.decode().split("\n")[0]
                if stream_url and stream_url.startswith('http'):
                    return (1, stream_url)
            await asyncio.sleep(1)
        return (0, "All format attempts failed")

    @capture_internal_err
    async def playlist(self, link: str, limit: int, user_id, videoid: Union[str, bool, None] = None) -> List[str]:
        if videoid:
            link = self.playlist_url + str(videoid)
        link = link.split("&")[0]
        _check_rate_limit()
        playlist = await shell_cmd(f"yt-dlp -i --get-id --flat-playlist --playlist-end {limit} --skip-download {link}")
        try:
            items = [key for key in playlist.split("\n") if key]
        except:
            items = []
        return items

    @capture_internal_err
    async def track(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[Dict, str]:
        try:
            info = await self._fetch_video_info(self._prepare_link(link, videoid))
            if not info:
                raise ValueError("Track not found via API")
        except Exception:
            _check_rate_limit()
            prepared = self._prepare_link(link, videoid)
            stdout, _ = await _exec_proc("yt-dlp", *(_cookies_args()), "--dump-json", prepared)
            if not stdout:
                raise ValueError("Track not found (yt-dlp fallback)")
            info = json.loads(stdout.decode())
        thumb = (info.get("thumbnail") or info.get("thumbnails", [{}])[0].get("url", "")).split("?")[0]
        _dur = info.get("duration")
        if isinstance(_dur, str) and _dur:
            duration_min = _dur
        elif isinstance(_dur, (int, float)) and _dur > 0:
            _secs = int(_dur)
            duration_min = f"{_secs // 60}:{_secs % 60:02d}"
        else:
            duration_min = None
        details = {
            "title": info.get("title", ""),
            "link": info.get("webpage_url", self._prepare_link(link, videoid)),
            "vidid": info.get("id", ""),
            "duration_min": duration_min,
            "thumb": thumb,
        }
        return details, info.get("id", "")

    @capture_internal_err
    async def formats(self, link: str, videoid: Union[str, bool, None] = None) -> Tuple[List[Dict], str]:
        link = self._prepare_link(link, videoid)
        key = f"f:{link}"
        now = time.time()
        async with _formats_lock:
            cached = _formats_cache.get(key)
            if cached and now - cached[0] < YOUTUBE_META_TTL:
                return cached[1], cached[2]

        _check_rate_limit()
        
        opts = {"quiet": True}
        cf = _cookiefile_path()
        if cf:
            opts["cookiefile"] = cf
        out: List[Dict] = []
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(link, download=False)
                for fmt in info.get("formats", []):
                    if "dash" in str(fmt.get("format", "")).lower():
                        continue
                    if not any(k in fmt for k in ("filesize", "filesize_approx")):
                        continue
                    if not all(k in fmt for k in ("format", "format_id", "ext", "format_note")):
                        continue
                    size = fmt.get("filesize") or fmt.get("filesize_approx")
                    if not size:
                        continue
                    out.append({
                        "format": fmt["format"],
                        "filesize": size,
                        "format_id": fmt["format_id"],
                        "ext": fmt["ext"],
                        "format_note": fmt["format_note"],
                        "yturl": link,
                    })
        except Exception:
            pass

        async with _formats_lock:
            if len(_formats_cache) > YOUTUBE_META_MAX:
                _formats_cache.clear()
            _formats_cache[key] = (now, out, link)

        return out, link

    @capture_internal_err
    async def slider(self, link: str, query_type: int, videoid: Union[str, bool, None] = None) -> Tuple[str, Optional[str], str, str]:
        data = await VideosSearch(self._prepare_link(link, videoid), limit=10).next()
        results = data.get("result", [])
        if not results or query_type >= len(results):
            raise IndexError(f"Query type index {query_type} out of range (found {len(results)} results)")
        r = results[query_type]
        return (
            r.get("title", ""),
            r.get("duration"),
            r.get("thumbnails", [{}])[0].get("url", "").split("?")[0],
            r.get("id", ""),
        )

    @capture_internal_err
    async def download(
        self,
        link: str,
        mystic,
        *,
        video: Union[bool, str, None] = None,
        videoid: Union[str, bool, None] = None,
        songaudio: Union[bool, str, None] = None,
        songvideo: Union[bool, str, None] = None,
        format_id: Union[bool, str, None] = None,
        title: Union[bool, str, None] = None,
    ) -> Union[Tuple[str, Optional[bool]], Tuple[None, None]]:
        link = self._prepare_link(link, videoid)
        video_id = link.split('v=')[-1].split('&')[0] if 'v=' in link else link
        
        extension = ".webm" if not video else ".mp4"
        common_file_path = os.path.join("downloads", f"{video_id}{extension}")
        
        # Direct-stream mode intentionally ignores existing local audio files
        # so manual play/autoplay can start immediately from the Fast API URL.
        if video and os.path.exists(common_file_path) and os.path.getsize(common_file_path) > 10240:
            print("✅ Local video cache")
            return common_file_path, True

        if songvideo or video:
            try:
                downloaded_file = await download_video(link)
                if downloaded_file:
                    print("✅ Video downloaded successfully")
                    if downloaded_file != common_file_path and downloaded_file.endswith('.mp4'):
                        try:
                            shutil.move(downloaded_file, common_file_path)
                            return common_file_path, True
                        except Exception:
                            return downloaded_file, True
                    return downloaded_file, True
            except Exception as e:
                print(f"❌ Video download error: {str(e)}")
            
            status, stream_url = await self.video(link)
            if status == 1:
                print("✅ Video stream")
                return stream_url, None
            else:
                return None, None

        else:
            # Fast-start VC mode:
            # Successful Fast API audio is streamed directly. Local files are
            # only used by fallback methods if the Fast API fails.
            try:
                audio_result = await download_audio(link)
                if audio_result:
                    if str(audio_result).startswith(("http://", "https://")):
                        print("🚀 Audio ready as direct stream")
                        return audio_result, None

                    print(f"✅ Audio fallback ready from local file: {audio_result}")
                    return audio_result, True
            except Exception as e:
                print(f"❌ Audio download error: {type(e).__name__}: {e!r}")
            
            try:
                p = await yt_dlp_download(link, type="audio")
                if p and os.path.exists(p) and os.path.getsize(p) > 10240:
                    print(f"✅ yt-dlp (original): {p}")
                    return p, True
            except Exception as e:
                print(f"❌ Original yt-dlp error: {str(e)}")
            
            try:
                p = await download_audio_concurrent(link)
                if p and os.path.exists(p) and os.path.getsize(p) > 10240:
                    print(f"✅ concurrent: {p}")
                    return p, True
            except Exception as e:
                print(f"❌ Concurrent download error: {str(e)}")
            
            print("❌ All audio download methods failed")
            return None, None

YouTube = YouTubeAPI()
