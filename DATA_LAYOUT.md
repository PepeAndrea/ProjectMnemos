# DATA_LAYOUT.md

| Path | Data | Persistent? | Default Retention | Safe to delete? |
|---|---|---|---|---|
| runtime/data/postgres/ | DB | Yes | explicit | No |
| runtime/media/audio/ | persisted audio | policy | policy | Caution |
| runtime/media/video/ | persisted video | policy | policy | Caution |
| runtime/media/keyframes/ | keyframes | Yes | policy | Caution |
| runtime/media/evidence/ | evidence | Yes | audit/policy | Caution |
| runtime/models/ | model weights | cache-like | until removed | Yes/re-download |
| runtime/cache/* | caches | No | cache | Yes |
| runtime/logs/ | telemetry | bounded | configurable | Yes |
| runtime/tmp/ | buffers/temp | No | minutes/session | Yes |
| runtime/datasets/ | replay fixtures | Yes | explicit | If backed up |
| runtime/exports/ | user exports | Yes | user | If copied elsewhere |

Rolling buffers belong in runtime/tmp or memory-backed equivalents, max 5 minutes experimentally.
Destructive purge must enumerate what will be deleted and require explicit confirmation.
