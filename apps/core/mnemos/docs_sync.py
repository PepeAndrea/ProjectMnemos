"""Drive-to-local sync with explicit snapshot transport and three-way hash checks."""

import argparse
import csv
import hashlib
import io
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from .drive_transport import GoogleDriveTransport, Snapshot, export_tables
from .plan_csv import normalized, plan_tables
from .runtime import ROOT


def digest(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def safe_local(root: Path, relative: str) -> Path:
    base = (root / "docs/source-of-truth").resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(base) or path == base:
        raise ValueError("mirror path escapes source-of-truth")
    return path


def state(local: str, remote: str, baseline: str | None) -> str:
    if local == remote:
        return "synced"
    if baseline is None:
        return "conflict"
    if local == baseline:
        return "drive-ahead"
    if remote == baseline:
        return "local-ahead"
    return "conflict"


def commit_mirror(root: Path, writes: list[tuple[Path, str]]) -> None:
    """Stage all output before replacement; restore previous bytes on local IO failure."""
    temp_root = root / "runtime/tmp"
    temp_root.mkdir(parents=True, exist_ok=True)
    originals = {path: path.read_bytes() if path.exists() else None for path, _ in writes}
    replaced: list[Path] = []
    with tempfile.TemporaryDirectory(dir=temp_root, prefix="docs-sync-") as directory:
        staged = []
        for index, (path, content) in enumerate(writes):
            temporary = Path(directory) / str(index)
            temporary.write_text(content)
            staged.append((path, temporary))
        try:
            for path, temporary in staged:
                path.parent.mkdir(parents=True, exist_ok=True)
                os.replace(temporary, path)
                replaced.append(path)
        except OSError:
            for path in reversed(replaced):
                original = originals[path]
                if original is None:
                    path.unlink(missing_ok=True)
                else:
                    path.write_bytes(original)
            raise


class DriveTransport(Protocol):
    def read(self, file_id: str) -> Snapshot: ...
    def write(self, file_id: str, expected: Snapshot, desired: Snapshot) -> Snapshot: ...


def sync(
    command: str,
    root: Path,
    snapshot: dict[str, Any] | None = None,
    explicit_intent: bool = False,
    transport: DriveTransport | None = None,
) -> list[dict[str, str]]:
    manifest_path = root / "docs/source-of-truth/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    if command == "push" and not explicit_intent:
        raise ValueError("docs:push requires explicit human intent")
    if transport is not None:
        snapshot = {
            source["drive_id"]: transport.read(source["drive_id"]) for source in manifest["sources"]
        }
    if command == "push" and transport is None:
        raise ValueError("docs:push requires a configured live write transport")
    results: list[dict[str, str]] = []
    writes: list[tuple[Path, str]] = []
    for source in manifest["sources"]:
        relative = source["local"]
        if relative.endswith("/"):
            relative = "docs/source-of-truth/03-operational-plan.txt"
        path = safe_local(root, relative)
        local_content = path.read_text() if path.exists() else ""
        local_hash = digest(local_content)
        if command == "verify":
            status = "verified" if source.get("sha256") == local_hash else "unverified"
        elif snapshot is None:
            status = "remote-unchecked"
        else:
            remote = snapshot[source["drive_id"]]
            remote_content = remote["content"].replace("\r\n", "\n")
            remote_hash = digest(remote_content)
            status = state(local_hash, remote_hash, source.get("sha256"))
            if command == "pull":
                if status in {"conflict", "local-ahead"}:
                    raise ValueError(f"refusing overwrite: {source['name']} {status}")
                writes.append((path, remote_content))
                source.update(
                    sha256=remote_hash,
                    modified_time=remote["modified_time"],
                    url=remote["url"],
                    synced_at=datetime.now(UTC).isoformat(),
                    local=relative,
                )
            if command == "push":
                if not explicit_intent:
                    raise ValueError("docs:push requires explicit human intent")
                if status in {"conflict", "drive-ahead"}:
                    raise ValueError("remote conflict blocks push")
                # Mark candidates only after the live transport and conflict preflight are available.
                status = "push-candidate" if status == "local-ahead" else "synced"
        results.append({"source": source["name"], "status": status})
    if command == "push" and not explicit_intent:
        raise ValueError("docs:push requires explicit human intent")
    # Every derived CSV participates in the same preflight as its native source.
    for source in manifest["sources"]:
        if source["name"] != "operational_plan":
            continue
        artifact_hashes = source.setdefault("artifact_sha256", {})
        if command == "verify":
            for name in ["milestones", "epics", "tasks"]:
                relative = "docs/source-of-truth/03-plan/" + name + ".csv"
                path = safe_local(root, relative)
                valid = path.exists() and digest(path.read_text()) == artifact_hashes.get(relative)
                results.append(
                    {
                        "source": "operational_plan/" + name,
                        "status": "verified" if valid else "unverified",
                    }
                )
        elif snapshot is not None:
            for name, content in plan_tables(snapshot[source["drive_id"]]).items():
                relative = "docs/source-of-truth/03-plan/" + name + ".csv"
                path = safe_local(root, relative)
                local_content = path.read_text() if path.exists() else ""
                baseline = artifact_hashes.get(relative)
                status = state(digest(local_content), digest(content), baseline)
                # Bootstrap only if the existing CSV is logically identical to Drive.
                if baseline is None and local_content and normalized(local_content) == content:
                    status = "synced"
                results.append({"source": "operational_plan/" + name, "status": status})
                if command == "push" and status in {"conflict", "drive-ahead"}:
                    raise ValueError("derived CSV conflict blocks push: " + relative)
                if command == "pull":
                    if status not in {"synced", "drive-ahead"} and path.exists():
                        raise ValueError("refusing derived CSV overwrite: " + relative)
                    writes.append((path, content))
                    artifact_hashes[relative] = digest(content)
    if command == "push":
        assert transport is not None and snapshot is not None
        for source in manifest["sources"]:
            expected = snapshot[source["drive_id"]]
            desired = {**expected, "content": safe_local(root, source["local"]).read_text()}
            if source["name"] == "operational_plan":
                desired["tables"] = {
                    name: list(
                        csv.reader(
                            io.StringIO(
                                safe_local(
                                    root, "docs/source-of-truth/03-plan/" + name + ".csv"
                                ).read_text()
                            )
                        )
                    )
                    for name in ["milestones", "epics", "tasks"]
                }
                desired["content"] = export_tables(desired["tables"])
                changed = plan_tables(desired) != plan_tables(expected)
            else:
                changed = desired["content"] != expected["content"]
            if not changed:
                continue
            updated = transport.write(source["drive_id"], expected, desired)
            # Post-write readback must match before the cached baseline advances.
            if source["name"] == "operational_plan":
                if plan_tables(updated) != plan_tables(desired):
                    raise ValueError("push readback differs from desired plan")
            elif updated["content"] != desired["content"]:
                raise ValueError("push readback differs from desired document")
            safe_local(root, source["local"]).write_text(updated["content"])
            source.update(
                sha256=digest(updated["content"]),
                modified_time=updated["modified_time"],
                synced_at=datetime.now(UTC).isoformat(),
            )
            if source["name"] == "operational_plan":
                for name, content in plan_tables(updated).items():
                    relative = "docs/source-of-truth/03-plan/" + name + ".csv"
                    safe_local(root, relative).write_text(content)
                    source["artifact_sha256"][relative] = digest(content)
            # Remote transactions are per file; retain each verified result if a later file fails.
            manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
            for row in results:
                if row["source"] == source["name"] or row["source"].startswith(
                    source["name"] + "/"
                ):
                    row["status"] = "pushed-verified"
    # Preflight every source before modifying any file.
    if command == "pull":
        if snapshot is None:
            raise ValueError("pull requires a freshly fetched Drive snapshot")
        commit_mirror(root, writes + [(manifest_path, json.dumps(manifest, indent=2) + "\n")])
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["pull", "status", "verify", "push"])
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--explicit-human-intent", action="store_true")
    parser.add_argument(
        "--live", action="store_true", help="Use explicitly configured OAuth transport"
    )
    args = parser.parse_args()
    snapshot = json.loads(args.snapshot.read_text()) if args.snapshot else None
    transport = (
        GoogleDriveTransport(os.environ.get("MNEMOS_DRIVE_OAUTH_TOKEN", "")) if args.live else None
    )
    result = sync(args.command, ROOT, snapshot, args.explicit_human_intent, transport)
    print(json.dumps(result, indent=2))
    if args.command == "verify" and any(row["status"] != "verified" for row in result):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
