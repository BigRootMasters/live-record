import os
import re
from datetime import datetime


def get_ffmpeg_bin():
    return os.getenv("FFMPEG_BIN", "ffmpeg")


def get_ffprobe_bin():
    return os.getenv("FFPROBE_BIN", "ffprobe")


def sanitize_path_component(value, fallback="recording"):
    cleaned = re.sub(r'[\\/:*?"<>|]+', "_", (value or "").strip())
    cleaned = re.sub(r"\s+", "_", cleaned)
    cleaned = cleaned.strip("._")
    return cleaned or fallback


def build_recording_output_path(base_path, anchor_id, anchor_name, started_at, media_type, extension):
    started_at = started_at or datetime.now()
    safe_anchor_name = sanitize_path_component(anchor_name, fallback=f"anchor_{anchor_id}")
    anchor_dir = f"{anchor_id}_{safe_anchor_name}"
    date_dir = started_at.strftime("%Y-%m-%d")
    filename = f"{started_at.strftime('%Y%m%d_%H%M%S')}.{extension}"
    return os.path.join(base_path, anchor_dir, date_dir, media_type, filename)
