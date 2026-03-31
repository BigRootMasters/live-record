import os


def get_ffmpeg_bin():
    return os.getenv("FFMPEG_BIN", "ffmpeg")


def get_ffprobe_bin():
    return os.getenv("FFPROBE_BIN", "ffprobe")
