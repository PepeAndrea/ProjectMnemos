import json

import pytest
from mnemos.docs_sync import digest, state, sync


def test_three_way_conflicts():
    assert state("same", "same", None) == "synced"
    assert state("old", "new", "old") == "drive-ahead"
    assert state("new", "old", "old") == "local-ahead"
    assert state("local", "remote", "old") == "conflict"


def setup(tmp_path):
    mirror = tmp_path / "docs/source-of-truth"
    mirror.mkdir(parents=True)
    (mirror / "a.md").write_text("old")
    (mirror / "manifest.json").write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "drive_id": "a",
                        "name": "a",
                        "local": "docs/source-of-truth/a.md",
                        "sha256": digest("old"),
                    }
                ]
            }
        )
    )
    return {
        "a": {"content": "new", "modified_time": "2026-10-08", "url": "https://drive.google.com/a"}
    }


def test_pull_verify_and_preserve_conflict(tmp_path):
    snapshot = setup(tmp_path)
    sync("pull", tmp_path, snapshot)
    assert sync("verify", tmp_path)[0]["status"] == "verified"
    path = tmp_path / "docs/source-of-truth/a.md"
    path.write_text("local edits")
    snapshot["a"]["content"] = "remote edits"
    with pytest.raises(ValueError, match="conflict"):
        sync("pull", tmp_path, snapshot)
    assert path.read_text() == "local edits"


def test_push_needs_intent_and_does_not_publish(tmp_path):
    snapshot = setup(tmp_path)
    with pytest.raises(ValueError):
        sync("push", tmp_path, snapshot)


def test_manifest_path_attack(tmp_path):
    snapshot = setup(tmp_path)
    path = tmp_path / "docs/source-of-truth/manifest.json"
    value = json.loads(path.read_text())
    value["sources"][0]["local"] = "../../secret"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError, match="escapes"):
        sync("pull", tmp_path, snapshot)


def test_plan_csv_updates_and_conflicts_are_atomic(tmp_path):
    mirror = tmp_path / "docs/source-of-truth"
    plan = mirror / "03-plan"
    plan.mkdir(parents=True)
    tables = {
        "milestones": [["Milestone ID", "Stato"], ["M0", "Not Started"]],
        "epics": [["Epic ID", "Stato"], ["E01", "Not Started"]],
        "tasks": [["Task ID", "Stato"], ["T001", "Not Started"]],
    }
    content = "plan export"
    (mirror / "03-operational-plan.txt").write_text(content)
    manifest = mirror / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "name": "operational_plan",
                        "drive_id": "plan",
                        "local": "docs/source-of-truth/03-operational-plan.txt",
                        "sha256": digest(content),
                    }
                ]
            }
        )
    )
    snapshot = {
        "plan": {"content": content, "tables": tables, "modified_time": "today", "url": "Drive"}
    }
    sync("pull", tmp_path, snapshot)
    assert all(row["status"] == "verified" for row in sync("verify", tmp_path))
    tables["tasks"][1][1] = "Done"
    sync("pull", tmp_path, snapshot)
    assert "T001,Done" in (plan / "tasks.csv").read_text()
    (plan / "tasks.csv").write_text("local edits")
    previous = manifest.read_text()
    tables["tasks"][1][1] = "Blocked"
    snapshot["plan"]["content"] = "new export"
    with pytest.raises(ValueError):
        sync("pull", tmp_path, snapshot)
    assert manifest.read_text() == previous
    assert (mirror / "03-operational-plan.txt").read_text() == content
    assert (plan / "tasks.csv").read_text() == "local edits"


class FakeDrive:
    def __init__(self, snapshot):
        self.snapshot = snapshot
        self.writes = []
        self.corrupt_readback = False

    def read(self, file_id):
        return dict(self.snapshot[file_id])

    def write(self, file_id, expected, desired):
        assert expected == self.snapshot[file_id]
        self.writes.append(file_id)
        result = {**desired, "modified_time": "new revision"}
        if self.corrupt_readback:
            result["content"] = "unexpected"
        self.snapshot[file_id] = result
        return result


def test_live_push_authorization_conflict_and_verified_baseline(tmp_path):
    snapshot = setup(tmp_path)
    snapshot["a"]["content"] = "old"
    transport = FakeDrive(snapshot)
    local = tmp_path / "docs/source-of-truth/a.md"
    local.write_text("approved edit")
    with pytest.raises(ValueError, match="human intent"):
        sync("push", tmp_path, explicit_intent=False, transport=transport)
    assert not transport.writes
    result = sync("push", tmp_path, explicit_intent=True, transport=transport)
    assert result[0]["status"] == "pushed-verified"
    assert sync("verify", tmp_path)[0]["status"] == "verified"
    assert transport.writes == ["a"]


def test_failed_push_readback_does_not_advance_baseline(tmp_path):
    snapshot = setup(tmp_path)
    snapshot["a"]["content"] = "old"
    transport = FakeDrive(snapshot)
    transport.corrupt_readback = True
    path = tmp_path / "docs/source-of-truth/manifest.json"
    previous = path.read_text()
    (tmp_path / "docs/source-of-truth/a.md").write_text("approved edit")
    with pytest.raises(ValueError, match="readback"):
        sync("push", tmp_path, explicit_intent=True, transport=transport)
    assert path.read_text() == previous


def test_filesystem_failure_restores_prior_mirror(tmp_path, monkeypatch):
    import os

    from mnemos.docs_sync import commit_mirror

    first, second = tmp_path / "first", tmp_path / "second"
    first.write_text("first old")
    second.write_text("second old")
    real_replace = os.replace

    def fail_second(source, target):
        if target == second:
            raise OSError("simulated full filesystem")
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", fail_second)
    with pytest.raises(OSError):
        commit_mirror(tmp_path, [(first, "first new"), (second, "second new")])
    assert first.read_text() == "first old" and second.read_text() == "second old"
