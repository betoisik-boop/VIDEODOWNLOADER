#!/usr/bin/env python3
"""Video Downloader - YouTube football skills & Pinterest summer vibes."""
import json
import logging
import shutil
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path


def _find_ffmpeg() -> str | None:
    """Locate ffmpeg across macOS / Linux / Windows / PyInstaller bundle."""
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        for name in ("ffmpeg.exe", "ffmpeg"):
            p = Path(bundled) / name
            if p.exists():
                return str(p)
    p = shutil.which("ffmpeg") or shutil.which("ffmpeg.exe")
    if p:
        return p
    here = Path(__file__).resolve().parent
    candidates = (
        here / "ffmpeg.exe",
        here / "bin" / "ffmpeg.exe",
        here / "ffmpeg",
        Path("/opt/homebrew/bin/ffmpeg"),
        Path("/usr/local/bin/ffmpeg"),
        Path("/opt/local/bin/ffmpeg"),
    )
    for cand in candidates:
        if cand.exists():
            return str(cand)
    return None


FFMPEG_PATH = _find_ffmpeg()

# ============================================================
# CONFIG - Edit these values to customize
# ============================================================

YOUTUBE_CHANNELS: list[str] = [
    # Add channel URLs via the GUI ("⚽ YouTube channels" panel) or here.
    # Example: "https://www.youtube.com/@SkillTwins"
]

# To find a Pinterest board URL: open pinterest.com, go to a board,
# copy the URL from the address bar. Format: https://www.pinterest.com/<user>/<board>/
PINTEREST_BOARDS = [
    # "https://www.pinterest.com/username/summer-vibes/",
]

# Keyword searches — downloads top N results from YouTube for each query.
# Example: "ronaldo skills", "messi dribbling compilation"
YOUTUBE_SEARCHES: list[str] = []

# Pinterest keyword searches — e.g. "summer vibes video", "aesthetic summer"
PINTEREST_SEARCHES: list[str] = []

DOWNLOAD_TIME = "09:00"          # 24h format, HH:MM
MAX_VIDEOS_PER_CHANNEL = 20
MAX_SEARCH_RESULTS = 10
MAX_PINTEREST_SEARCH_RESULTS = 20
QUALITY = "1080p"                # 720p, 1080p, 1440p, 2160p, best

# "title" = name files by video title (readable)
# "id"    = name files by video id / url slug (short, unique)
YOUTUBE_FILENAME = "title"
PINTEREST_FILENAME = "id"

# ============================================================
# Paths
# ============================================================

BASE_DIR = Path.home() / "VideoDownloader"
FOOTBALL_DIR = BASE_DIR / "football_skills"
SUMMER_DIR = BASE_DIR / "summer_vibes"
LOG_DIR = BASE_DIR / "logs"
ARCHIVE_DIR = BASE_DIR / "archives"
MP3_DIR = BASE_DIR / "mp3"
SINGLE_DIR = BASE_DIR / "pinterest_single"

for d in (FOOTBALL_DIR, SUMMER_DIR, LOG_DIR, ARCHIVE_DIR, MP3_DIR, SINGLE_DIR):
    d.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / "downloader.log"
CONFIG_FILE = BASE_DIR / "config.json"


def load_user_config() -> None:
    """Merge GUI-managed URLs and settings from config.json."""
    global YOUTUBE_CHANNELS, PINTEREST_BOARDS, YOUTUBE_SEARCHES, PINTEREST_SEARCHES
    global DOWNLOAD_TIME, MAX_VIDEOS_PER_CHANNEL, MAX_SEARCH_RESULTS
    global MAX_PINTEREST_SEARCH_RESULTS, QUALITY
    global YOUTUBE_FILENAME, PINTEREST_FILENAME
    if not CONFIG_FILE.exists():
        return
    try:
        data = json.loads(CONFIG_FILE.read_text())
    except Exception:
        return
    YOUTUBE_CHANNELS = list(dict.fromkeys(
        list(YOUTUBE_CHANNELS) + list(data.get("youtube_channels") or [])))
    PINTEREST_BOARDS = list(dict.fromkeys(
        list(PINTEREST_BOARDS) + list(data.get("pinterest_boards") or [])))
    YOUTUBE_SEARCHES = list(dict.fromkeys(
        list(YOUTUBE_SEARCHES) + list(data.get("youtube_searches") or [])))
    PINTEREST_SEARCHES = list(dict.fromkeys(
        list(PINTEREST_SEARCHES) + list(data.get("pinterest_searches") or [])))
    DOWNLOAD_TIME = data.get("download_time") or DOWNLOAD_TIME
    MAX_VIDEOS_PER_CHANNEL = int(data.get("max_videos_per_channel") or MAX_VIDEOS_PER_CHANNEL)
    MAX_SEARCH_RESULTS = int(data.get("max_search_results") or MAX_SEARCH_RESULTS)
    MAX_PINTEREST_SEARCH_RESULTS = int(
        data.get("max_pinterest_search_results") or MAX_PINTEREST_SEARCH_RESULTS)
    QUALITY = data.get("quality") or QUALITY
    YOUTUBE_FILENAME = data.get("youtube_filename") or YOUTUBE_FILENAME
    PINTEREST_FILENAME = data.get("pinterest_filename") or PINTEREST_FILENAME


load_user_config()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("downloader")


class _YdlLogger:
    """Forward yt-dlp's debug/info/warning/error to our logger with a prefix."""
    def __init__(self, prefix: str):
        self.prefix = prefix
    def debug(self, msg: str) -> None:
        if msg.startswith("[debug]"):
            return
        # yt-dlp routes most info messages through .debug
        log.info(f"{self.prefix}: {msg}")
    def info(self, msg: str) -> None:
        log.info(f"{self.prefix}: {msg}")
    def warning(self, msg: str) -> None:
        log.warning(f"{self.prefix}: {msg}")
    def error(self, msg: str) -> None:
        log.error(f"{self.prefix}: {msg}")


def _quality_format(q: str) -> str:
    if q == "best":
        return "bestvideo+bestaudio/best"
    height = "".join(c for c in q if c.isdigit()) or "1080"
    return f"bestvideo[height<={height}]+bestaudio/best[height<={height}]"


def download_youtube() -> None:
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        log.error("yt-dlp not installed. Run setup.sh.")
        return

    if not YOUTUBE_CHANNELS and not YOUTUBE_SEARCHES:
        log.info("No YouTube channels or searches configured.")
        return

    archive = ARCHIVE_DIR / "youtube.txt"
    base_opts = {
        "format": _quality_format(QUALITY),
        "download_archive": str(archive),
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
    }
    if FFMPEG_PATH:
        base_opts["ffmpeg_location"] = FFMPEG_PATH

    yt_name = "%(title)s" if YOUTUBE_FILENAME == "title" else "%(id)s"
    channel_opts = {
        **base_opts,
        "outtmpl": str(FOOTBALL_DIR / "%(channel)s" / f"{yt_name}.%(ext)s"),
        "playlistend": MAX_VIDEOS_PER_CHANNEL,
    }
    for channel in YOUTUBE_CHANNELS:
        log.info(f"YouTube channel: {channel}")
        try:
            with YoutubeDL(channel_opts) as ydl:
                ydl.download([channel])
        except Exception as e:
            log.error(f"YouTube failed for {channel}: {e}")

    yt_search_name = "%(title)s [%(id)s]" if YOUTUBE_FILENAME == "title" else "%(id)s"
    search_opts = {
        **base_opts,
        "outtmpl": str(FOOTBALL_DIR / "_searches" / f"{yt_search_name}.%(ext)s"),
        "playlistend": MAX_SEARCH_RESULTS,
    }
    for query in YOUTUBE_SEARCHES:
        q = query.strip()
        if not q:
            continue
        log.info(f"YouTube search: {q}")
        try:
            with YoutubeDL(search_opts) as ydl:
                ydl.download([f"ytsearch{MAX_SEARCH_RESULTS}:{q}"])
        except Exception as e:
            log.error(f"YouTube search failed for {q!r}: {e}")


def pinterest_search_urls(query: str, limit: int) -> list[str]:
    """Call Pinterest's public search endpoint, return pin URLs (videos preferred)."""
    data_param = json.dumps({
        "options": {
            "query": query,
            "scope": "pins",
            "page_size": max(limit * 3, 25),
        },
        "context": {},
    }, separators=(",", ":"))
    qs = urllib.parse.urlencode({
        "source_url": f"/search/pins/?q={urllib.parse.quote(query)}",
        "data": data_param,
    })
    url = "https://www.pinterest.com/resource/BaseSearchResource/get/?" + qs
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "XMLHttpRequest",
        "X-APP-VERSION": "cb1fcba",
        "X-Pinterest-AppState": "active",
        "X-Pinterest-PWS-Handler": "www/search/[scope].js",
        "Referer": f"https://www.pinterest.com/search/pins/?q={urllib.parse.quote(query)}",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except Exception as e:
        log.error(f"Pinterest search HTTP failed for {query!r}: {e}")
        return []

    results = (payload.get("resource_response") or {}).get("data") or {}
    results = results.get("results") if isinstance(results, dict) else results
    if not isinstance(results, list):
        return []

    video_urls: list[str] = []
    image_urls: list[str] = []
    for r in results:
        if not isinstance(r, dict):
            continue
        pid = r.get("id")
        if not pid:
            continue
        pin_url = f"https://www.pinterest.com/pin/{pid}/"
        is_video = bool(r.get("videos")) or r.get("is_video") or \
                   (r.get("pin_type") == "video") or r.get("story_pin_data")
        (video_urls if is_video else image_urls).append(pin_url)

    chosen = video_urls[:limit]
    if len(chosen) < limit:
        chosen += image_urls[: limit - len(chosen)]
    return chosen


def download_pinterest() -> None:
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        log.error("yt-dlp not installed. Run setup.sh.")
        return

    if not PINTEREST_BOARDS and not PINTEREST_SEARCHES:
        log.info("No Pinterest boards or searches configured.")
        return

    archive = ARCHIVE_DIR / "pinterest.txt"
    base_opts = {
        "format": _quality_format(QUALITY),
        "download_archive": str(archive),
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
    }
    if FFMPEG_PATH:
        base_opts["ffmpeg_location"] = FFMPEG_PATH

    pn_name = "%(title)s [%(id)s]" if PINTEREST_FILENAME == "title" else "%(id)s"
    board_opts = {
        **base_opts,
        "outtmpl": str(SUMMER_DIR / f"{pn_name}.%(ext)s"),
        "playlistend": MAX_VIDEOS_PER_CHANNEL,
    }
    for board in PINTEREST_BOARDS:
        log.info(f"Pinterest board/pin: {board}")
        try:
            with YoutubeDL(board_opts) as ydl:
                ydl.download([board])
        except Exception as e:
            log.error(f"Pinterest failed for {board}: {e}")

    for query in PINTEREST_SEARCHES:
        q = query.strip()
        if not q:
            continue
        log.info(f"Pinterest search: {q} (up to {MAX_PINTEREST_SEARCH_RESULTS})")
        urls = pinterest_search_urls(q, MAX_PINTEREST_SEARCH_RESULTS)
        if not urls:
            log.warning(f"Pinterest search returned 0 results for {q!r}")
            continue
        log.info(f"Pinterest search found {len(urls)} pins")
        safe = "".join(c if c.isalnum() or c in "-_ " else "_" for c in q)[:40].strip() or "search"
        search_opts = {
            **base_opts,
            "outtmpl": str(SUMMER_DIR / "_searches" / safe / f"{pn_name}.%(ext)s"),
        }
        try:
            with YoutubeDL(search_opts) as ydl:
                ydl.download(urls)
        except Exception as e:
            log.error(f"Pinterest search download failed for {q!r}: {e}")


def download_youtube_mp4(url: str, quality: str | None = None) -> bool:
    """Download a single YouTube URL as MP4 video."""
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        log.error("yt-dlp not installed.")
        return False
    out_dir = BASE_DIR / "mp4"
    out_dir.mkdir(parents=True, exist_ok=True)
    yt_name = "%(title)s" if YOUTUBE_FILENAME == "title" else "%(id)s"
    opts = {
        "format": _quality_format(quality or QUALITY),
        "outtmpl": str(out_dir / f"{yt_name}.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "ignoreerrors": False,
        "quiet": True,
        "no_warnings": False,
        "logger": _YdlLogger("MP4"),
    }
    if FFMPEG_PATH:
        opts["ffmpeg_location"] = FFMPEG_PATH
    log.info(f"MP4 download: {url} (ffmpeg: {FFMPEG_PATH or 'NOT FOUND'})")
    try:
        with YoutubeDL(opts) as ydl:
            rc = ydl.download([url])
        if rc == 0:
            log.info(f"MP4 saved to {out_dir}")
            return True
        log.error(f"MP4 download returned non-zero status ({rc}).")
        return False
    except Exception as e:
        log.error(f"MP4 failed: {e}")
        return False


def download_youtube_mp3(url: str, bitrate: str | None = None) -> bool:
    """Download a single YouTube URL as MP3 audio."""
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        log.error("yt-dlp not installed.")
        return False
    br = (bitrate or "192").rstrip("k")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(MP3_DIR / "%(title)s.%(ext)s"),
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": br,
        }],
        "noplaylist": True,
        "keepvideo": False,
        "ignoreerrors": False,
        "quiet": True,
        "no_warnings": False,
        "logger": _YdlLogger("MP3"),
    }
    if FFMPEG_PATH:
        opts["ffmpeg_location"] = FFMPEG_PATH
    else:
        log.error("ffmpeg not found — MP3 conversion requires ffmpeg. "
                  "Run setup.bat (Windows) or `brew install ffmpeg` (macOS).")
        return False
    log.info(f"MP3 download: {url} (ffmpeg: {FFMPEG_PATH})")
    try:
        with YoutubeDL(opts) as ydl:
            rc = ydl.download([url])
        if rc == 0:
            log.info(f"MP3 saved to {MP3_DIR}")
            return True
        log.error(f"MP3 download returned non-zero status ({rc}).")
        return False
    except Exception as e:
        log.error(f"MP3 failed: {e}")
        return False


def _pinterest_image_fallback(url: str) -> bool:
    """When yt-dlp can't handle a pin (image-only), scrape og:image."""
    import re
    m = re.search(r"/pin/(\d+)", url)
    pin_id = m.group(1) if m else "pin"
    req = urllib.request.Request(url, headers={
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"),
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8", errors="replace")
    except Exception as e:
        log.error(f"Pinterest fetch failed: {e}")
        return False
    mi = re.search(r'<meta[^>]+property="og:image"[^>]+content="([^"]+)"', html) \
        or re.search(r'<meta[^>]+content="([^"]+)"[^>]+property="og:image"', html)
    if not mi:
        log.error("Could not find og:image on pin page.")
        return False
    img_url = mi.group(1).replace("&amp;", "&")
    ext = img_url.rsplit(".", 1)[-1].split("?")[0].lower()
    if ext not in ("jpg", "jpeg", "png", "webp", "gif"):
        ext = "jpg"
    dest = SINGLE_DIR / f"{pin_id}.{ext}"
    try:
        urllib.request.urlretrieve(img_url, dest)
        log.info(f"Pinterest image saved: {dest}")
        return True
    except Exception as e:
        log.error(f"Image download failed: {e}")
        return False


def download_pinterest_single(url: str) -> bool:
    """Download a single Pinterest URL — video first, image fallback."""
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        log.error("yt-dlp not installed.")
        return False
    log.info(f"Pinterest single: {url}")
    opts = {
        "format": _quality_format(QUALITY),
        "outtmpl": str(SINGLE_DIR / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "ignoreerrors": True,
        "quiet": True,
        "no_warnings": True,
    }
    if FFMPEG_PATH:
        opts["ffmpeg_location"] = FFMPEG_PATH
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if info is not None:
                log.info(f"Pinterest video saved to {SINGLE_DIR}")
                return True
    except Exception as e:
        log.warning(f"yt-dlp couldn't download video ({e}); trying image fallback")
    return _pinterest_image_fallback(url)


def run_once(platform: str = "all") -> None:
    started = datetime.now()
    log.info(f"=== Download run ({platform}) started at {started.isoformat(timespec='seconds')} ===")
    if platform in ("all", "youtube"):
        download_youtube()
    if platform in ("all", "pinterest"):
        download_pinterest()
    elapsed = (datetime.now() - started).total_seconds()
    log.info(f"=== Run finished in {elapsed:.1f}s ===")


def run_scheduler() -> None:
    try:
        import schedule
    except ImportError:
        log.error("schedule not installed. Run setup.sh.")
        sys.exit(1)

    schedule.every().day.at(DOWNLOAD_TIME).do(run_once)
    log.info(f"Scheduler started. Next run daily at {DOWNLOAD_TIME}.")
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    args = sys.argv[1:]
    if "--schedule" in args:
        run_scheduler()
        sys.exit(0)
    mp3_url = None
    mp4_url = None
    single_url = None
    quality = None
    bitrate = None
    platform = "all"
    for a in args:
        if a.startswith("--yt-mp3="):
            mp3_url = a.split("=", 1)[1]
        elif a.startswith("--yt-mp4="):
            mp4_url = a.split("=", 1)[1]
        elif a.startswith("--pinterest-single="):
            single_url = a.split("=", 1)[1]
        elif a.startswith("--quality="):
            quality = a.split("=", 1)[1]
        elif a.startswith("--bitrate="):
            bitrate = a.split("=", 1)[1]
        elif a.startswith("--platform="):
            platform = a.split("=", 1)[1]
    if mp4_url:
        sys.exit(0 if download_youtube_mp4(mp4_url, quality) else 1)
    if mp3_url:
        sys.exit(0 if download_youtube_mp3(mp3_url, bitrate) else 1)
    if single_url:
        sys.exit(0 if download_pinterest_single(single_url) else 1)
    run_once(platform)
