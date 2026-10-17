"""Model weight availability + safe download (timeout, retries, checksum, atomic write)."""
from __future__ import annotations

import hashlib
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from .errors import ModelDownloadError


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def model_status(path: Path, expected_sha256: str | None) -> dict:
    exists = path.is_file()
    status = {
        "available": exists,
        "path": str(path),
        "size_bytes": path.stat().st_size if exists else None,
        "checksum_ok": None,
    }
    if exists and expected_sha256:
        status["checksum_ok"] = sha256_of(path) == expected_sha256
    return status


def download_model(
    url: str,
    dest: Path,
    expected_sha256: str | None = None,
    timeout: float = 30.0,
    retries: int = 2,
    opener: Callable = urllib.request.urlopen,
) -> Path:
    """Download to dest atomically. Raises ModelDownloadError with a clear cause."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_name(dest.name + ".part")
    manual = f"Download it manually from {url} and save it as {dest}."
    last_err = "unknown error"

    for attempt in range(1, retries + 2):
        try:
            h = hashlib.sha256()
            with opener(url, timeout=timeout) as resp, open(part, "wb") as out:
                while True:
                    chunk = resp.read(1 << 16)
                    if not chunk:
                        break
                    h.update(chunk)
                    out.write(chunk)
            if part.stat().st_size == 0:
                raise ModelDownloadError(f"Downloaded file was empty. {manual}")
            if expected_sha256 and h.hexdigest() != expected_sha256:
                part.unlink(missing_ok=True)
                raise ModelDownloadError(
                    "Checksum mismatch: the downloaded file is not the expected model "
                    f"(got {h.hexdigest()[:12]}…, expected {expected_sha256[:12]}…). {manual}"
                )
            part.replace(dest)
            return dest
        except ModelDownloadError:
            raise  # integrity failures are not retried
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code} {e.reason}"
        except urllib.error.URLError as e:
            last_err = f"network error: {e.reason}"
        except (TimeoutError, OSError) as e:
            last_err = f"{type(e).__name__}: {e}"
        part.unlink(missing_ok=True)

    raise ModelDownloadError(
        f"Model download failed after {retries + 1} attempt(s) ({last_err}). {manual}"
    )
