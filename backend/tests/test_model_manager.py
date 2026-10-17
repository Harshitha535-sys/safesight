import hashlib
import io
import urllib.error

import pytest

from app.cv.errors import ModelDownloadError
from app.cv.model_manager import download_model, model_status


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def test_status_missing(tmp_path):
    st = model_status(tmp_path / "m.onnx", "abc")
    assert st["available"] is False and st["checksum_ok"] is None


def test_download_success_with_checksum(tmp_path):
    data = b"weights" * 100
    dest = tmp_path / "sub" / "m.onnx"
    download_model("http://x", dest, hashlib.sha256(data).hexdigest(),
                   opener=lambda url, timeout: FakeResp(data))
    assert dest.read_bytes() == data
    assert not dest.with_name("m.onnx.part").exists()


def test_checksum_mismatch_is_rejected_and_not_saved(tmp_path):
    dest = tmp_path / "m.onnx"
    with pytest.raises(ModelDownloadError, match="Checksum mismatch"):
        download_model("http://x", dest, "0" * 64, opener=lambda url, timeout: FakeResp(b"other"))
    assert not dest.exists() and not dest.with_name("m.onnx.part").exists()


def test_network_failure_is_retried_then_reported(tmp_path):
    calls = []

    def opener(url, timeout):
        calls.append(1)
        raise urllib.error.URLError("Name or service not known")

    dest = tmp_path / "m.onnx"
    with pytest.raises(ModelDownloadError) as e:
        download_model("http://example.invalid/m.onnx", dest, None, retries=2, opener=opener)
    assert len(calls) == 3
    assert "Name or service not known" in e.value.message
    assert "manually" in e.value.message
    assert not dest.exists()


def test_http_error_reported(tmp_path):
    def opener(url, timeout):
        raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)

    with pytest.raises(ModelDownloadError, match="HTTP 404"):
        download_model("http://x", tmp_path / "m.onnx", None, retries=0, opener=opener)
