import os

from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer


def _get_serializer():
    secret_key = os.getenv("SECRET_KEY", "default_secret_key")
    return URLSafeTimedSerializer(secret_key, salt="transcription-media")


def _allowed_roots():
    return [
        os.path.abspath(os.getenv("SUMMARY_STORAGE_PATH", "./data/summaries")),
        os.path.abspath(os.getenv("VIDEO_STORAGE_PATH", "./data/temp_videos")),
    ]


def generate_media_token(file_path):
    absolute_path = os.path.abspath(file_path)
    if not _is_allowed_path(absolute_path):
        raise ValueError(f"file path is not allowed: {file_path}")
    return _get_serializer().dumps({"path": absolute_path})


def resolve_media_token(token, max_age=3600):
    try:
        payload = _get_serializer().loads(token, max_age=max_age)
    except (BadSignature, BadTimeSignature):
        return None

    absolute_path = os.path.abspath(payload.get("path") or "")
    if not absolute_path or not os.path.exists(absolute_path):
        return None
    if not _is_allowed_path(absolute_path):
        return None
    return absolute_path


def _is_allowed_path(absolute_path):
    for root in _allowed_roots():
        try:
            common_path = os.path.commonpath([absolute_path, root])
        except ValueError:
            continue
        if common_path == root:
            return True
    return False
