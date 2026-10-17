"""CLI: python -m app.cv.fetch_model   (downloads + verifies the YOLOX-nano weights)"""
import sys

from ..config import settings
from .errors import ModelDownloadError
from .model_manager import download_model, model_status


def main() -> int:
    st = model_status(settings.model_path, settings.model_sha256)
    if st["available"] and st["checksum_ok"] is not False:
        print(f"Model already present: {st['path']} ({st['size_bytes']} bytes)")
        return 0
    try:
        p = download_model(settings.model_url, settings.model_path, settings.model_sha256)
    except ModelDownloadError as e:
        print(f"ERROR: {e.message}", file=sys.stderr)
        return 1
    print(f"Downloaded and verified: {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
