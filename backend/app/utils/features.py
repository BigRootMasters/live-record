import os


def _get_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_transcription_enabled():
    return _get_bool_env("ENABLE_TRANSCRIPTION", default=False)
