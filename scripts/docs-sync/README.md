# Canonical synchronization

Run from repository root with the official Python environment:

```sh
runtime/core-venv/bin/python -m mnemos.docs_sync status
runtime/core-venv/bin/python -m mnemos.docs_sync verify
runtime/core-venv/bin/python -m mnemos.docs_sync pull --snapshot runtime/tmp/drive-snapshot.json
```

Snapshots are freshly fetched maps keyed by Drive ID, containing content, modified_time and url.
The operational plan accepts three native tables or the connector CSV export. Pull derives all
three plan CSVs and preflights their hashes as well as document hashes. Local IO failure restores
previous bytes. Verify checks five source files and all three derived CSVs; it fails on mismatch.
Status without a live source explicitly reports remote-unchecked.

For explicitly configured OAuth, use --live and MNEMOS_DRIVE_OAUTH_TOKEN in the process environment.
Never extract connected-app credentials or print tokens. Live push also requires
--explicit-human-intent, supplied only after actual human authorization to publish canonical edits.
No remote upload is authorized by a general implementation goal.

Native Docs push supports unique paragraph replacements with requiredRevisionId; structural,
ambiguous or cascading changes are rejected. Native Sheets push supports same-shape cell edits
with stable row IDs and headers, preserves formatting/unchanged formulas, and uses observed tab
names. Sheets has no Docs revision CAS: collaborators must pause edits for an authorized push.
All files are conflict-preflighted; remote transactions are per file, and verified earlier uploads
retain their baseline if a later file fails. Readback mismatch never advances that file's baseline.
Implementation is verified with simulated transport/API responses. Live OAuth roundtrip remains
pending; canonical Drive has not been modified. Implementation progress is docs/plan/progress.json.
