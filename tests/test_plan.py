import csv
import json

import pytest
from mnemos.plan import dependencies, next_tasks


def test_canonical_range_dependencies():
    assert dependencies("T001:T004,T007") == {"T001", "T002", "T003", "T004", "T007"}
    with pytest.raises(ValueError):
        dependencies("T004:T001")


def test_done_cannot_skip_dependencies(tmp_path):
    base = tmp_path / "docs/source-of-truth/03-plan"
    base.mkdir(parents=True)
    with (base / "tasks.csv").open("w") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["Task ID", "Milestone", "Priorità", "Dipendenze"]
        )
        writer.writeheader()
        writer.writerows(
            [
                {"Task ID": "T001", "Milestone": "M0", "Priorità": "P0", "Dipendenze": ""},
                {"Task ID": "T002", "Milestone": "M0", "Priorità": "P0", "Dipendenze": "T001"},
            ]
        )
    ledger = tmp_path / "docs/plan"
    ledger.mkdir()
    assert next_tasks(tmp_path) == ["T001"]
    (ledger / "progress.json").write_text(
        json.dumps({"T002": {"status": "Done", "evidence": ["test"]}})
    )
    with pytest.raises(ValueError, match="dependencies"):
        next_tasks(tmp_path)
