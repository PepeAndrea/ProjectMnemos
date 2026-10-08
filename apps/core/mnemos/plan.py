"""Local evidence ledger; canonical Drive plan remains untouched."""

import csv
import json
import re
from pathlib import Path

from .runtime import ROOT


def dependencies(expression: str) -> set[str]:
    result: set[str] = set()
    for token in filter(None, re.split(r"[,;\s]+", expression.strip())):
        if ":" in token:
            first, last = token.split(":")
            if not re.fullmatch(r"T\d{3}", first) or not re.fullmatch(r"T\d{3}", last):
                raise ValueError("invalid task range")
            start, end = int(first[1:]), int(last[1:])
            if start > end:
                raise ValueError("inverted task range")
            result.update(f"T{number:03}" for number in range(start, end + 1))
        elif re.fullmatch(r"T\d{3}", token):
            result.add(token)
        else:
            raise ValueError("invalid dependency")
    return result


def next_tasks(root: Path = ROOT) -> list[str]:
    tasks = list(csv.DictReader((root / "docs/source-of-truth/03-plan/tasks.csv").open()))
    ledger_path = root / "docs/plan/progress.json"
    ledger = json.loads(ledger_path.read_text()) if ledger_path.exists() else {}
    done = {task_id for task_id, entry in ledger.items() if entry["status"] == "Done"}
    all_ids = {row["Task ID"] for row in tasks}
    for row in tasks:
        deps = dependencies(row.get("Dipendenze") or "")
        if not deps <= all_ids:
            raise ValueError("unknown task dependency")
        if row["Task ID"] in done and not deps <= done:
            raise ValueError("Done task has incomplete dependencies: " + row["Task ID"])
        if row["Task ID"] in done and not ledger[row["Task ID"]].get("evidence"):
            raise ValueError("Done task lacks objective evidence")
    eligible = [
        row
        for row in tasks
        if row["Task ID"] not in done
        and dependencies(row.get("Dipendenze") or "") <= done
        and ledger.get(row["Task ID"], {}).get("status") != "Blocked"
    ]
    eligible.sort(key=lambda row: (row["Priorità"], row["Milestone"], row["Task ID"]))
    return [row["Task ID"] for row in eligible]


def main() -> None:
    print(json.dumps({"next_unblocked": next_tasks()}, indent=2))


if __name__ == "__main__":
    main()
