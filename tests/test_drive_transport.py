import pytest
from mnemos.drive_transport import GoogleDriveTransport, document_replacements, export_tables
from mnemos.plan_csv import plan_tables


def test_native_document_patches_preserve_structure():
    requests = document_replacements(
        "Title\nApproved old paragraph\n", "Title\nApproved new paragraph\n"
    )
    assert requests == [
        {
            "replaceAllText": {
                "containsText": {"text": "Approved old paragraph", "matchCase": True},
                "replaceText": "Approved new paragraph",
            }
        }
    ]
    with pytest.raises(ValueError, match="structural"):
        document_replacements("Title\n", "Title\nNew chapter\n")
    with pytest.raises(ValueError, match="ambiguous"):
        document_replacements("Title\nSame\nSame\nEnd\n", "Title\nChanged\nChanged\nEnd\n")


def test_sheet_roundtrip_and_oauth_missing():
    tables = {
        "milestones": [["Milestone ID", "Stato"], ["M0", "Not Started"]],
        "epics": [["Epic ID", "Stato"], ["E01", "Not Started"]],
        "tasks": [["Task ID", "Stato"], ["T001", "Not Started"]],
    }
    assert plan_tables({"content": export_tables(tables)}) == plan_tables({"tables": tables})
    with pytest.raises(PermissionError):
        GoogleDriveTransport("")
