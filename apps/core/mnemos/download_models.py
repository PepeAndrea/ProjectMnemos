"""Reproducible downloads of explicitly registered permissive model weights."""

import hashlib
import json
import urllib.request
from collections.abc import Callable
from pathlib import Path

from .model_inventory import ALLOWED, model_record
from .runtime import ROOT, RuntimeLayout


def fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        data = response.read(256 * 1024 * 1024 + 1)
    if len(data) > 256 * 1024 * 1024:
        raise ValueError("download exceeds registered baseline model budget")
    return bytes(data)


def download(name: str, root: Path = ROOT, fetch: Callable[[str], bytes] = fetch_bytes) -> Path:
    manifest = json.loads((root / "docs/models.json").read_text())
    records = [entry for entry in manifest["models"] if entry["name"] == name]
    if len(records) != 1:
        raise ValueError("unknown or duplicate model")
    record = records[0]
    if record.get("code_license") not in ALLOWED or record.get("weight_license") not in ALLOWED:
        raise PermissionError("unapproved model license")
    if not record.get("license_source") or not record.get("revision"):
        raise PermissionError("missing license provenance")
    url = record["url"]
    allowed_origins = (
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/",
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/",
        "https://huggingface.co/ggml-org/whisper-vad/resolve/",
    )
    if not url.startswith(allowed_origins) or "/" + record["revision"] + "/" not in url:
        raise ValueError("unregistered model download origin")
    path = RuntimeLayout(root).path(record["runtime_path"])
    if path.exists():
        try:
            model_record(name, root)
            return path
        except ValueError:
            pass
    data = fetch(url)
    if len(data) != record["bytes"] or hashlib.sha256(data).hexdigest() != record["sha256"]:
        raise ValueError("download size/checksum mismatch; existing model preserved")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".download")
    try:
        temporary.write_bytes(data)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    model_record(name, root)
    return path


def main() -> None:
    for name in [
        entry["name"] for entry in json.loads((ROOT / "docs/models.json").read_text())["models"]
    ]:
        print(download(name).relative_to(ROOT))


if __name__ == "__main__":
    main()
