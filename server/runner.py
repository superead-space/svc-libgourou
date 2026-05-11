import asyncio
import logging
import time
from pathlib import Path
from typing import Optional

from server import settings
from server.models import DedrmRequest

logger = logging.getLogger("svc-libgourou.runner")

_semaphore: Optional[asyncio.Semaphore] = None


def get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(settings.MAX_CONCURRENT)
    return _semaphore


class PathValidationError(ValueError):
    pass


def _resolve_under_data(rel: str, *, must_exist: bool = False) -> Path:
    if not rel:
        raise PathValidationError("Path must not be empty")
    if rel.startswith("/"):
        raise PathValidationError(f"Path must be relative, got absolute: {rel!r}")
    if "\x00" in rel:
        raise PathValidationError("Path contains null byte")

    candidate = (settings.DATA_DIR / rel).resolve()
    try:
        candidate.relative_to(settings.DATA_DIR)
    except ValueError:
        raise PathValidationError(f"Path escapes DATA_DIR: {rel!r}")

    if must_exist and not candidate.is_file():
        raise PathValidationError(f"File not found: {rel!r}")
    return candidate


def _validate_filename(name: str) -> None:
    if not name:
        raise PathValidationError("output_file must not be empty")
    if "/" in name or "\\" in name:
        raise PathValidationError(f"output_file must not contain path separators: {name!r}")
    if name in (".", "..") or name.startswith("."):
        raise PathValidationError(f"output_file must not start with '.': {name!r}")


async def _run_subprocess(
    args: list, *, timeout: int
) -> tuple:
    logger.info(f"exec {' '.join(args)}")
    proc = await asyncio.create_subprocess_exec(
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_b, stderr_b = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        try:
            await proc.wait()
        except Exception:
            pass
        raise

    stdout = stdout_b.decode("utf-8", errors="replace")
    stderr = stderr_b.decode("utf-8", errors="replace")
    return proc.returncode, stdout, stderr


async def run_dedrm(req: DedrmRequest) -> dict:
    acsm_path = _resolve_under_data(req.acsm_file, must_exist=True)
    drm_path = _resolve_under_data(req.drm_file)
    output_dir = _resolve_under_data(req.output_dir)
    _validate_filename(req.output_file)

    drm_path.parent.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path_abs = output_dir / req.output_file
    output_path_rel = str(output_path_abs.relative_to(settings.DATA_DIR))

    sem = get_semaphore()
    start = time.monotonic()

    async with sem:
        rc, stdout, stderr = await _run_subprocess(
            [
                "acsmdownloader",
                "--adept-directory", str(settings.ADEPT_DIR),
                "--output-file", str(drm_path),
                str(acsm_path),
            ],
            timeout=settings.REQUEST_TIMEOUT,
        )
        if rc != 0:
            return {
                "ok": False,
                "stage": "acsmdownloader",
                "exit_code": rc,
                "stderr": (stderr.strip() or stdout.strip())[:4000],
            }

        rc, stdout, stderr = await _run_subprocess(
            [
                "adept_remove",
                "--adept-directory", str(settings.ADEPT_DIR),
                "--output-file", str(output_path_abs),
                str(drm_path),
            ],
            timeout=settings.REQUEST_TIMEOUT,
        )
        if rc != 0:
            return {
                "ok": False,
                "stage": "adept_remove",
                "exit_code": rc,
                "stderr": (stderr.strip() or stdout.strip())[:4000],
            }

    duration_ms = int((time.monotonic() - start) * 1000)
    return {
        "ok": True,
        "output_path": output_path_rel,
        "duration_ms": duration_ms,
    }


async def get_libgourou_version() -> str:
    try:
        rc, stdout, stderr = await _run_subprocess(
            ["acsmdownloader", "--version"], timeout=5
        )
    except Exception:
        return "unknown"
    text = (stdout.strip() or stderr.strip())
    if not text:
        return "unknown"
    return text.splitlines()[-1].strip() or "unknown"
