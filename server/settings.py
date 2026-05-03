import os
from pathlib import Path


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


DATA_DIR: Path = Path(os.environ.get("DATA_DIR", "/home/libgourou/files")).resolve()
ADEPT_DIR: Path = Path(os.environ.get("ADEPT_DIR", "/home/libgourou/.adept")).resolve()
REQUEST_TIMEOUT: int = _int_env("REQUEST_TIMEOUT", 180)
MAX_CONCURRENT: int = max(1, _int_env("MAX_CONCURRENT", 1))
LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "info").upper()
