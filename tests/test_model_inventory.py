import hashlib
import json

import pytest
from mnemos.model_inventory import model_record


def test_weight_license_and_hash_gate(tmp_path):
    models = tmp_path / "runtime/models"
    models.mkdir(parents=True)
    (models / "test.bin").write_bytes(b"safe")
    docs = tmp_path / "docs"
    docs.mkdir()
    record = {
        "name": "test",
        "code_license": "MIT",
        "weight_license": "noncommercial",
        "runtime_path": "models/test.bin",
        "license_source": "official",
        "revision": "1",
        "sha256": hashlib.sha256(b"safe").hexdigest(),
    }
    manifest = docs / "models.json"
    manifest.write_text(json.dumps({"models": [record]}))
    with pytest.raises(PermissionError):
        model_record("test", tmp_path)
    record["weight_license"] = "MIT"
    manifest.write_text(json.dumps({"models": [record]}))
    assert model_record("test", tmp_path)["path"] == models / "test.bin"
    (models / "test.bin").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        model_record("test", tmp_path)


def test_corrupt_download_preserves_existing_model(tmp_path):
    from mnemos.download_models import download

    path = tmp_path / "runtime/models/test.bin"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"existing")
    docs = tmp_path / "docs"
    docs.mkdir()
    record = {
        "name": "test",
        "code_license": "MIT",
        "weight_license": "MIT",
        "license_source": "official",
        "revision": "1",
        "runtime_path": "models/test.bin",
        "url": "https://media.githubusercontent.com/media/opencv/opencv_zoo/1/model",
        "bytes": 4,
        "sha256": hashlib.sha256(b"safe").hexdigest(),
    }
    (docs / "models.json").write_text(json.dumps({"models": [record]}))
    with pytest.raises(ValueError, match="checksum"):
        download("test", tmp_path, lambda url: b"bad")
    assert path.read_bytes() == b"existing"
    assert download("test", tmp_path, lambda url: b"safe") == path
