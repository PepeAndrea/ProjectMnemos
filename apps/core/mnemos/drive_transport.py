"""Native Drive/Docs/Sheets transport. OAuth comes only from explicit runtime config."""

import csv
import difflib
import io
import json
import urllib.parse
import urllib.request
from typing import Any

from .plan_csv import HEADERS, plan_tables

Snapshot = dict[str, Any]


def export_tables(tables: dict[str, list[list[str]]]) -> str:
    chunks = []
    for name in HEADERS:
        stream = io.StringIO(newline="")
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerow([""] + tables[name][0])
        writer.writerows([[str(index)] + row for index, row in enumerate(tables[name][1:])])
        chunks.append(stream.getvalue())
    return "\f".join(chunks)


def document_replacements(old: str, new: str) -> list[dict[str, Any]]:
    """Preserve native document structure; reject insert/delete/repeated paragraph ambiguity."""
    old_lines, new_lines = old.splitlines(), new.splitlines()
    changes: list[dict[str, Any]] = []
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    for tag, a, b, c, d in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag != "replace" or b - a != d - c:
            raise ValueError("structural document edits require an explicit native edit plan")
        for before, after in zip(old_lines[a:b], new_lines[c:d], strict=True):
            if not before or not after or old.count(before) != 1:
                raise ValueError("ambiguous paragraph replacement")
            changes.append(
                {
                    "replaceAllText": {
                        "containsText": {"text": before, "matchCase": True},
                        "replaceText": after,
                    }
                }
            )
    needles = [change["replaceAllText"]["containsText"]["text"] for change in changes]
    for index, change in enumerate(changes):
        replacement = change["replaceAllText"]["replaceText"]
        if any(needle in replacement for other, needle in enumerate(needles) if other != index):
            raise ValueError("cascading paragraph replacement requires native edit plan")
    if not changes and old != new:
        raise ValueError("unsupported whitespace/line-ending-only document edit")
    return changes


def column_label(index: int) -> str:
    label = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        label = chr(65 + remainder) + label
    return label


class GoogleDriveTransport:
    def __init__(self, token: str):
        if not token:
            raise PermissionError("MNEMOS_DRIVE_OAUTH_TOKEN is not configured")
        self.token = token

    def request(self, url: str, payload: dict[str, Any] | None = None) -> Any:
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode() if payload else None,
            headers={"Authorization": "Bearer " + self.token, "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read(10 * 1024 * 1024 + 1)
        if len(data) > 10 * 1024 * 1024:
            raise ValueError("Drive response exceeds sync budget")
        return json.loads(data) if not "/export?" in url else data.decode("utf-8")

    def metadata(self, file_id: str) -> dict[str, Any]:
        result: dict[str, Any] = self.request(
            "https://www.googleapis.com/drive/v3/files/"
            + urllib.parse.quote(file_id, safe="")
            + "?fields=id,name,mimeType,modifiedTime,version"
        )
        return result

    def read(self, file_id: str) -> Snapshot:
        metadata = self.metadata(file_id)
        escaped = urllib.parse.quote(file_id, safe="")
        result: Snapshot = {
            "url": "https://drive.google.com/file/d/" + escaped + "/view",
            "modified_time": metadata["modifiedTime"],
            "version": metadata["version"],
            "mime_type": metadata["mimeType"],
        }
        if metadata["mimeType"] == "application/vnd.google-apps.document":
            doc = self.request("https://docs.googleapis.com/v1/documents/" + escaped)
            result["revision_id"] = doc["revisionId"]
            result["content"] = self.request(
                "https://www.googleapis.com/drive/v3/files/"
                + escaped
                + "/export?mimeType=text%2Fplain"
            ).replace("\r\n", "\n")
        elif metadata["mimeType"] == "application/vnd.google-apps.spreadsheet":
            sheet = self.request(
                "https://sheets.googleapis.com/v4/spreadsheets/"
                + escaped
                + "?fields=sheets(properties(title,gridProperties))"
            )
            ranges = []
            titles = []
            for tab in sheet["sheets"]:
                props = tab["properties"]
                grid = props["gridProperties"]
                if grid["rowCount"] * grid["columnCount"] > 50000:
                    raise ValueError("plan sheet exceeds bounded sync cells")
                title = props["title"]
                titles.append(title)
                ranges.append(
                    "'"
                    + title.replace("'", "''")
                    + "'!A1:"
                    + column_label(grid["columnCount"])
                    + str(grid["rowCount"])
                )
            query = urllib.parse.urlencode(
                [("ranges", r) for r in ranges] + [("valueRenderOption", "FORMULA")]
            )
            values = self.request(
                "https://sheets.googleapis.com/v4/spreadsheets/"
                + escaped
                + "/values:batchGet?"
                + query
            )
            tables, tab_titles = {}, {}
            for title, value_range in zip(titles, values["valueRanges"], strict=True):
                rows = [[str(cell) for cell in row] for row in value_range.get("values", [])]
                name = next(
                    (key for key, header in HEADERS.items() if rows and rows[0][0] == header), None
                )
                if name is None or name in tables:
                    raise ValueError("unexpected plan tab or duplicate table")
                tables[name], tab_titles[name] = rows, title
            plan_tables({"tables": tables})
            result.update(tables=tables, tab_titles=tab_titles, content=export_tables(tables))
        else:
            raise ValueError("unsupported canonical file type")
        # Refuse snapshots assembled while native content was changing.
        if self.metadata(file_id)["version"] != metadata["version"]:
            raise ValueError("Drive changed during snapshot read")
        return result

    def write(self, file_id: str, expected: Snapshot, desired: Snapshot) -> Snapshot:
        actual = self.read(file_id)
        if actual["version"] != expected["version"] or actual["content"] != expected["content"]:
            raise ValueError("remote changed after push review")
        escaped = urllib.parse.quote(file_id, safe="")
        if actual["mime_type"] == "application/vnd.google-apps.document":
            changes = document_replacements(actual["content"], desired["content"])
            if changes:
                self.request(
                    "https://docs.googleapis.com/v1/documents/" + escaped + ":batchUpdate",
                    {
                        "requests": changes,
                        "writeControl": {"requiredRevisionId": actual["revision_id"]},
                    },
                )
        else:
            before, after = plan_tables(actual), plan_tables(desired)
            edits = []
            for name in HEADERS:
                old = list(csv.reader(io.StringIO(before[name])))
                new = list(csv.reader(io.StringIO(after[name])))
                if (
                    len(old) != len(new)
                    or old[0] != new[0]
                    or [r[0] for r in old] != [r[0] for r in new]
                ):
                    raise ValueError("plan structural changes require an explicit native edit plan")
                title = actual["tab_titles"][name].replace("'", "''")
                for row_index, (old_row, new_row) in enumerate(zip(old, new, strict=True), 1):
                    for col_index, (old_cell, new_cell) in enumerate(
                        zip(old_row, new_row, strict=True), 1
                    ):
                        if old_cell != new_cell:
                            edits.append(
                                {
                                    "range": "'"
                                    + title
                                    + "'!"
                                    + column_label(col_index)
                                    + str(row_index),
                                    "values": [[new_cell]],
                                }
                            )
            if edits:
                # Sheets has no Docs-style revision writeControl; narrow RAW cell patches preserve
                # formulas and formatting. Preflight detects conflicts; external editing must pause.
                self.request(
                    "https://sheets.googleapis.com/v4/spreadsheets/"
                    + escaped
                    + "/values:batchUpdate",
                    {"valueInputOption": "RAW", "data": edits},
                )
        updated = self.read(file_id)
        if actual["mime_type"] == "application/vnd.google-apps.document":
            verified = updated["content"] == desired["content"]
        else:
            verified = plan_tables(updated) == plan_tables(desired)
        if not verified:
            raise ValueError("remote write did not verify; baseline not advanced")
        return updated
