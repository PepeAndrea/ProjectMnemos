"""Canonical Sheets export to deterministic executable CSV mirrors."""

import csv
import io
from typing import Any

HEADERS = {"milestones": "Milestone ID", "epics": "Epic ID", "tasks": "Task ID"}


def csv_text(rows: list[list[str]]) -> str:
    if not rows:
        raise ValueError("empty plan table")
    width = len(rows[0])
    if len(set(rows[0])) != width or any(not value for value in rows[0]):
        raise ValueError("invalid plan headers")
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, lineterminator="\n")
    for row in rows:
        if len(row) > width:
            raise ValueError("plan row wider than its header")
        writer.writerow(row + [""] * (width - len(row)))
    return stream.getvalue()


def normalized(content: str) -> str:
    rows = [[value or "" for value in row] for row in csv.reader(io.StringIO(content)) if row]
    return csv_text(rows)


def plan_tables(snapshot: dict[str, Any]) -> dict[str, str]:
    tables = snapshot.get("tables")
    if tables is None:
        tables = {}
        for block in snapshot["content"].split("\f"):
            rows = list(csv.reader(io.StringIO(block.strip())))
            if not rows:
                continue
            # Connector text hydration adds a leading dataframe index column.
            if rows[0][0] == "":
                rows = [row[1:] for row in rows]
            name = next((key for key, header in HEADERS.items() if rows[0][0] == header), None)
            if name is None or name in tables:
                raise ValueError("unknown or duplicate canonical plan table")
            tables[name] = rows
    if set(tables) != set(HEADERS):
        raise ValueError("plan requires milestones, epics and tasks")
    result = {}
    for name, rows in tables.items():
        if not rows or rows[0][0] != HEADERS[name]:
            raise ValueError("unexpected canonical table header")
        ids = [row[0] for row in rows[1:] if row]
        if any(not key for key in ids) or len(set(ids)) != len(ids):
            raise ValueError("duplicate or missing plan identifiers")
        result[name] = csv_text(rows)
    return result
