# INSTALLATION_REGISTRY.md

Update whenever Mnemos installs/downloads a significant dependency, model, runtime, system package, certificate, service or large asset.

| Component | Version / Hash | Purpose | Install Method | Location | Approx Size | Required? | License | Removal |
|---|---|---|---|---|---:|---|---|---|
| Docker Desktop | TBD | Infra runtime | system | outside repo | TBD | DB | vendor terms | uninstall Docker Desktop |
| Python | 3.11.x | Core | uv/system | outside repo + .venv | TBD | Yes | PSF | remove env/install if project-only |
| Node.js | TBD LTS | Web | system manager | outside repo | TBD | Yes | MIT | remove if project-only |
| PostgreSQL + pgvector | TBD | DB/vector search | Docker | image + runtime/data/postgres | TBD | Yes | permissive | compose down + remove |
| EmbeddingGemma 2 | TBD | Multimodal embeddings | project downloader | runtime/models | TBD | benchmark | Apache-2.0 | delete model folder |
| Detector | TBD | Generic objects | project downloader | runtime/models | TBD | Yes | TBD | delete model folder |
| YuNet/SFace | TBD | Enrolled faces | project downloader | runtime/models | TBD | planned | verify permissive terms | delete model folder |
| whisper.cpp model | TBD | Local ASR | project downloader | runtime/models | TBD | planned | runtime/model-specific | delete model folder |
| LAN certificate/CA | TBD | HTTPS phone capture | setup script | trust store + runtime | tiny | phone mode | N/A | revoke/untrust/remove |

Also record brew/pipx/global npm/pnpm installs, certificates, macOS permission setup, caches and exact uninstall instructions.
