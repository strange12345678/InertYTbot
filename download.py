# download.py
import os, uuid, asyncio, subprocess
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError
from config import YTDLP_OPTS_BASE, DOWNLOAD_DIR, SPLIT_CHUNK_SIZE
from functions.utils import human_size

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def list_video_qualities(info):
    formats = info.get("formats", []) or []
    video_formats = []
    for f in formats:
        if f.get("vcodec") == "none":
            continue
        h = f.get("height") or 0
        label = f"{h}p" if h else f.get("format_note") or f.get("format_id")
        video_formats.append({"format_id": f.get("format_id"), "label": label, "height": h, "filesize": f.get("filesize") or f.get("filesize_approx") or 0})
    dedup = {}
    for v in video_formats:
        key = v["height"] or v["label"]
        if key not in dedup or (v["filesize"] and v["filesize"] < dedup[key]["filesize"]):
            dedup[key] = v
    sorted_list = sorted(dedup.values(), key=lambda x: (x["height"] if isinstance(x["height"], int) else 0))
    return [(x["label"], x["format_id"]) for x in sorted_list]

def list_audio_qualities(info):
    formats = info.get("formats", []) or []
    audio_formats = []
    for f in formats:
        if f.get("acodec") and f.get("vcodec") == "none":
            abr = f.get("abr") or f.get("tbr") or 0
            label = f"{int(abr)}kbps" if abr else f.get("format_note") or f.get("format_id")
            audio_formats.append({"format_id": f.get("format_id"), "label": label, "abr": abr, "filesize": f.get("filesize") or f.get("filesize_approx") or 0})
    dedup = {}
    for a in audio_formats:
        key = a["abr"] or a["label"]
        if key not in dedup or (a["filesize"] and a["filesize"] < dedup[key]["filesize"]):
            dedup[key] = a
    sorted_list = sorted(dedup.values(), key=lambda x: (x["abr"] if isinstance(x["abr"], (int,float)) else 0))
    return [(x["label"], x["format_id"]) for x in sorted_list]

# Progress hook generator that calls an async callback
def make_progress_hook(async_update_cb, session_id):
    loop = asyncio.get_event_loop()
    def _hook(d):
        status = d.get("status")
        if status == "downloading":
            per = d.get("_percent_str","").strip()
            speed = d.get("_speed_str","") or ""
            downloaded = d.get("downloaded_bytes") or 0
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            eta = d.get("eta")
            text = (f"📥 Downloading: {per}\n⬇️ Speed: {speed}\n📦 {human_size(downloaded)} / {human_size(total)}\n⏱️ ETA: {eta}s")
            loop.call_soon_threadsafe(asyncio.ensure_future, async_update_cb(session_id, text))
        elif status == "finished":
            loop.call_soon_threadsafe(asyncio.ensure_future, async_update_cb(session_id, "✅ Download finished, preparing upload..."))
    return _hook

# Blocking function to run in executor (safe)
def download_blocking(url, format_id, is_audio, async_update_cb):
    outtmpl = os.path.join(DOWNLOAD_DIR, "%(title)s.%(ext)s")
    opts = dict(YTDLP_OPTS_BASE)
    opts.update({"format": format_id, "outtmpl": outtmpl, "progress_hooks":[make_progress_hook(async_update_cb, str(uuid.uuid4()))]})
    if is_audio:
        opts.update({"postprocessors":[{"key":"FFmpegExtractAudio","preferredcodec":"mp3","preferredquality":"192"}]})
    with YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        if is_audio and opts.get("postprocessors"):
            base, _ = os.path.splitext(filename)
            filename = base + ".mp3"
        size = os.path.getsize(filename) if os.path.exists(filename) else 0
        return {"filepath": filename, "title": info.get("title"), "filesize": size}

# Async wrapper to run safely in thread
async def download_and_prepare(url, format_id, is_audio, async_update_cb):
    return await asyncio.to_thread(download_blocking, url, format_id, is_audio, async_update_cb)

# Splitting helper
def split_file(filepath, chunk_size=SPLIT_CHUNK_SIZE):
    parts = []
    base = os.path.basename(filepath)
    dirn = os.path.dirname(filepath)
    try:
        prefix = os.path.join(dirn, base + ".part_")
        # use split binary if present
        subprocess.check_call(["split", "-b", str(chunk_size), filepath, prefix])
        for f in sorted([os.path.join(dirn, x) for x in os.listdir(dirn) if x.startswith(base + ".part_")]):
            parts.append(f)
    except Exception:
        # fallback python split
        with open(filepath, "rb") as f:
            idx = 0
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                part_path = f"{filepath}.part{idx}"
                with open(part_path, "wb") as pf:
                    pf.write(chunk)
                parts.append(part_path)
                idx += 1
    return parts
