"""Fail-closed model inventory: code and weight licenses are independent."""

import hashlib
import json
from pathlib import Path
from typing import Any

from .runtime import ROOT, RuntimeLayout

ALLOWED = {"Apache-2.0", "MIT", "BSD-3-Clause", "BSD-2-Clause"}


def model_record(name: str, root: Path = ROOT) -> dict[str, Any]:
    manifest = json.loads((root / "docs/models.json").read_text())
    records = [entry for entry in manifest["models"] if entry["name"] == name]
    if len(records) != 1:
        raise ValueError("unknown or duplicate model registration")
    record: dict[str, Any] = records[0]
    if record.get("code_license") not in ALLOWED or record.get("weight_license") not in ALLOWED:
        raise PermissionError("unapproved code or weight license")
    if not record.get("license_source") or not record.get("revision"):
        raise PermissionError("missing license provenance or version")
    path = RuntimeLayout(root).path(record["runtime_path"])
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    if sha.hexdigest() != record.get("sha256"):
        raise ValueError("model checksum mismatch")
    return {**record, "path": path}
