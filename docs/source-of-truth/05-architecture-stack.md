Project Mnemos
Architettura e Stack Tecnologico


1. Obiettivo tecnico
Project Mnemos deve funzionare inizialmente su un MacBook Apple Silicon M1 con 8 GB di RAM, in installazione single-user e local-first. Il sistema deve poter evolvere in seguito verso un personal server più potente senza cambiare i contratti di dominio, le API o il modello dati.


2. Principi architetturali
- modular monolith per il core;
- processi e servizi separati solo dove servono davvero;
- event-driven internamente con code bounded e backpressure;
- local-first per perception, memoria, storage e controlli;
- cloud event-driven e non continuo;
- provider interfaces per modelli e servizi sostituibili;
- nessuna dipendenza da uno specifico modello proprietario per i contratti applicativi;
- single-user installation, nessun multi-tenant nell'MVP;
- tutto il runtime applicativo persistente deve stare sotto la directory del progetto quando tecnicamente possibile.


3. Topologia iniziale
Processi principali:
- mnemos-core: daemon Python, API FastAPI, orchestration, world state, memory, decision routing, action engine;
- mnemos-web: dashboard React;
- postgres: PostgreSQL + pgvector in Docker Compose;
- optional workers: processi Python separati solo per workload ML pesanti quando il benchmark dimostra un beneficio.


Il core espone:
- REST per CRUD e query;
- WebSocket per eventi realtime, stato, transcript e controllo;
- endpoint di signaling WebRTC per il browser mobile;
- API interne typed per perception, memory e action.


4. Linguaggi e toolchain
Backend/core:
- Python 3.11 come baseline compatibile con ML tooling;
- FastAPI;
- Uvicorn;
- Pydantic v2;
- SQLAlchemy 2;
- Alembic;
- asyncio;
- uv per environment e dependency management.


Frontend:
- TypeScript;
- React;
- Vite, preferito a Next.js perché la UI è una SPA locale senza necessità SSR;
- pnpm;
- WebSocket client per eventi;
- WebRTC browser APIs per satellite phone.


5. Repository
Monorepo unico.


Struttura iniziale consigliata:
apps/core
apps/web
packages/contracts
packages/python
docs
scripts
runtime
tests
infra


AGENTS.md e CODEX.md risiedono nella root.


6. Docker e runtime nativo
Docker Compose viene usato per infrastruttura riproducibile:
- PostgreSQL + pgvector;
- eventuali servizi futuri realmente necessari.


I componenti ML e media che beneficiano di accesso diretto a Metal/MPS, camera, microfono o filesystem locale possono girare nativamente sul Mac.


Il principio non è "tutto nel container", ma "tutto riproducibile e contenuto". Docker Desktop, Python e tool di sistema inevitabili possono esistere fuori repository; ogni installazione esterna deve essere registrata in INSTALLATION_REGISTRY.md.


7. Layout dati locale
Tutto ciò che Mnemos genera viene concentrato sotto:
runtime/
  data/
    postgres/
  media/
    audio/
    video/
    keyframes/
    evidence/
  models/
  cache/
    huggingface/
    torch/
    onnx/
    ocr/
  logs/
  tmp/
  datasets/
  exports/


Variabili di ambiente devono reindirizzare le cache esterne verso queste directory quando possibile.


8. Database
PostgreSQL + pgvector è il database principale.


Modello dati concettuale:
- entities;
- entity_references;
- observations;
- tracks;
- conversations;
- utterances;
- semantic_facts;
- episodes;
- prospective_memories;
- reminders;
- tasks;
- relationships;
- evidence;
- actions;
- action_audit;
- sources/devices;
- model_runs.


Le relazioni del knowledge graph vengono inizialmente modellate in PostgreSQL. Neo4j o altro graph DB viene introdotto solo se benchmark/query reali dimostrano un vantaggio necessario.


9. Media storage
Default MVP:
- filesystem locale sotto runtime/media.


L'applicazione usa un MediaStore interface, con implementazioni:
- LocalMediaStore;
- S3CompatibleMediaStore, predisposta ma non obbligatoria nell'MVP.


Questo permette in futuro S3, R2 o storage equivalente senza cambiare il dominio.


10. Event architecture
Nell'MVP non vengono introdotti Kafka, NATS o Redis per il solo fatto di avere eventi.
Si usa:
- asyncio.Queue bounded;
- typed domain events;
- retry policy dove serve;
- persistence degli eventi importanti;
- backpressure esplicita.


Un EventBus interface permette una futura sostituzione con NATS/Redis Streams se il sistema diventerà multi-processo o distribuito.


11. Video ingestion
Tutte le fonti implementano un contratto VideoSource comune:
- LocalCameraSource;
- VideoFileSource;
- PhoneWebRTCSource;
- future SmartGlassesSource;
- future RTSPSource.


Ogni frame normalizzato contiene:
- source_id;
- monotonic timestamp;
- wall-clock timestamp;
- dimensions;
- pixel format;
- sequence;
- optional calibration/context metadata.


12. Browser phone satellite
Nell'MVP lo smartphone non richiede app nativa.


Flow:
1. il Mac genera sessione di pairing e QR;
2. il telefono apre una pagina web HTTPS sulla LAN;
3. l'utente autorizza camera e microfono;
4. il browser crea una connessione WebRTC col core;
5. audio e video arrivano al Mac;
6. WebSocket/WebRTC DataChannel trasferiscono stato, telemetry e controllo;
7. Tobi può inviare risposta testuale/audio al telefono.


La pagina mobile deve supportare:
- camera front/back;
- preview;
- start/pause/stop;
- stato connessione;
- TTS output;
- telemetria;
- eventuale torch/zoom quando supportato.


HTTPS è obbligatorio per usare getUserMedia in un secure context su dispositivo remoto. Il bootstrap locale deve quindi prevedere certificato LAN attendibile e relativa procedura di setup.


13. WebRTC
WebRTC è il protocollo MVP scelto per browser phone -> Mac perché fornisce:
- audio/video realtime;
- A/V synchronization;
- congestion control;
- jitter buffering;
- codec negotiation;
- futura estensione ICE/STUN/TURN.


Signaling:
- FastAPI WebSocket.


Ricezione Python:
- aiortc o equivalente mantenuto dietro un MediaTransport interface.


Internet/TURN è fuori dal primo MVP.


14. Target media e latency
Trasporto iniziale:
- 720p;
- fino a 30 FPS;
- bitrate adattivo;
- qualità privilegiata verso bassa latenza.


La perception pipeline non deve elaborare ogni frame per forza. Il frame scheduler può campionare dinamicamente in base a carico, scene change, tracking e task.


Target iniziale:
- feed mobile->Mac percepito realtime;
- p95 ingest latency misurata;
- detection overlay target <500 ms end-to-end ove possibile sul M1;
- degradazione controllata se il carico supera il budget.


15. Rolling buffers
Audio: fino a 5 minuti.
Video: fino a 5 minuti se memoria e storage lo permettono; qualità/bitrate possono essere inferiori allo stream live.


I buffer sono circolari e non persistenti. Una porzione diventa persistente solo tramite:
- Recording/Meeting mode;
- Evidence mode;
- comando utente;
- event policy.


16. Object detection
Il sistema usa un DetectorProvider interface.


Baseline preferita per sviluppo e futura distribuzione proprietaria:
- modello con licenza permissiva e runtime ONNX/CoreML-friendly;
- benchmark iniziale tra YOLOX/RT-DETR family o equivalenti appropriati al Mac M1.


Ultralytics può essere usato come adapter sperimentale soltanto con licensing tracciato; non deve diventare una dipendenza irreversibile del prodotto.


17. Tracking
Tracking iniziale:
- ByteTrack o tracker equivalente;
- track lifecycle enter/update/exit;
- binding tra track e resolved entity;
- evitare entity recognition a ogni frame quando una track è già risolta con alta confidence.


18. OCR
OCRProvider interface.
Baseline:
- PaddleOCR/PP-OCR compatibile col runtime scelto;
- italiano e inglese;
- OCR event-driven su ROI, non full-frame continuo.


Document reading completo viene supportato come modalità dedicata, non come costo continuo.


19. Face detection e recognition
Solo persone esplicitamente registrate possono avere identità persistente.


Baseline commercial-friendly:
- face detection: YuNet o equivalente;
- face embedding/recognition: OpenCV SFace o equivalente con licenza permissiva.


InsightFace pretrained weights non devono essere introdotti nel prodotto senza verifica licenza.


Unknown faces:
- anonymous session track;
- nessun nome persistente;
- retention limitata.


20. Speaker identity
Voice enrollment dell'utente principale è richiesto.


Speaker layer:
- VAD;
- ASR;
- diarization;
- speaker embedding;
- association con visual face tracks quando disponibile.


La diarizzazione può essere approssimativa online e raffinata in background/fine-session. L'accuratezza finale di memoria prevale sulla latenza della label speaker.


21. ASR
Il sistema deve supportare italiano e inglese.


ASRProvider interface.
Baseline Mac:
- whisper.cpp o runtime locale equivalente ottimizzato Apple Silicon;
- partial transcript volatile;
- final transcript persistibile/event-driven.


Cloud transcription è fallback opzionale, non requisito di funzionamento.


22. TTS
TTSProvider interface.


MVP:
- TTS locale del sistema operativo / browser;
- output su Mac e/o telefono.


Futuro:
- ElevenLabs adapter;
- altri provider streaming low-latency.


23. EmbeddingGemma 2
EmbeddingGemma 2 è il candidato primario per MultimodalEmbeddingProvider.


Modalità:
- text;
- image;
- audio;
- video/moments quando appropriato.


Uso:
- memory search;
- cross-modal retrieval;
- semantic candidate retrieval;
- OCR/text indexing;
- zero-shot routing sperimentale.


Dimensione vettore:
- non hardcoded prima del benchmark;
- confrontare 256/512/768;
- default provvisorio 256 solo se recall e precisione soddisfano i test.


Sul Mac M1 8 GB:
- lazy loading;
- caricare solo le modality necessarie;
- unload/eviction se la memory pressure supera soglia;
- niente modello full sempre residente senza benchmark.


24. Object instance identity
EmbeddingGemma 2 non sostituisce da solo instance verification.


Resolver:
1. detector;
2. crop;
3. multimodal embedding candidate search;
4. local feature verification;
5. OCR/mark/attribute evidence;
6. temporal continuity;
7. historical/context evidence;
8. fused confidence.


LocalFeatureMatcher interface.
La scelta tra ORB/SIFT/LightGlue/SuperPoint o alternative viene fatta tramite benchmark e license audit.


25. Search
SearchEngine combina:
- SQL structured filters;
- pgvector similarity;
- full-text search;
- entity graph relations;
- temporal filters;
- provenance/evidence.


La UI espone:
- browsing tradizionale;
- query unificata "Ask Tobi".


26. World State
Il core mantiene una HotMemory in-process:
- active people;
- visible entities;
- active tracks;
- current conversation;
- current speakers;
- current topic;
- recent utterances;
- recent events;
- pending reminders;
- current focus.


TTL e dimensioni sono bounded.


27. Decision pipeline
DecisionProvider interface.


Cascata:
Level 0:
- regole deterministiche;
- thresholds;
- state machine.


Level 1A:
- local semantic routing;
- EmbeddingGemma 2 zero-shot routing dove benchmarkato.


Level 1B:
- OpenAI Decisions API;
- gpt-6-luna;
- predicate/choice/score;
- testo o immagine selezionata;
- event-driven.


Level 2:
- OpenAI Responses API;
- modello configurabile;
- structured outputs;
- reasoning, extraction complessa, planning, explanation.


Le decisioni ad alto impatto non vengono mai eseguite direttamente dal modello: passano da Policy Engine.


28. Cloud data policy
Default:
- biometric embeddings restano locali;
- raw continuous audio/video non viene inviato al cloud;
- transcript/event state può essere inviato quando necessario;
- singoli frame/crop possono essere inviati a un vision-capable cloud model per unknown-object fallback se policy/config lo consentono;
- ogni cloud call deve essere osservabile e categorizzata.


29. Unknown object fallback
Se detection/entity resolution non basta:
- selezionare un keyframe/crop;
- opzionalmente chiamare un VLM cloud;
- ottenere descrizione/candidate label;
- chiedere conferma quando necessario;
- registrare provenance;
- non confondere descrizione semantica con identity verification.


30. Action Engine
ActionProposal è separata da ActionExecution.


Risk levels:
- automatic;
- automatic-with-audit;
- user-confirmation;
- strong-confirmation;
- prohibited/out-of-scope.


MVP:
- local task;
- local reminder;
- memory update;
- notification;
- draft action interfaces.


Email/calendar/CRM reali vengono aggiunti dopo che memory + reasoning + policy sono stabili.


31. API contracts
Contratti condivisi devono essere versionati.


Esempi:
- FrameEvent;
- AudioChunk;
- Detection;
- TrackUpdate;
- EntityCandidate;
- EntityResolution;
- Observation;
- Utterance;
- ConversationUpdate;
- MemoryCandidate;
- ReminderTrigger;
- DecisionRequest/DecisionResult;
- ActionProposal/ActionResult.


JSON Schema/OpenAPI generato dal backend è source per il client TypeScript dove praticabile.


32. Dashboard
Dashboard MVP completa:
- live camera feed;
- detection/identity overlays;
- transcript live;
- source/device state;
- event timeline;
- entity catalog;
- entity detail;
- last seen;
- conversations;
- memories;
- tasks/reminders;
- Ask Tobi;
- model/runtime status;
- storage/cost telemetry;
- settings/privacy;
- debug/evidence view.


33. Security
MVP security:
- local-only by default;
- pairing token one-time/short-lived;
- authenticated device session;
- CSRF/origin protections;
- HTTPS mobile page;
- secrets in .env not committed;
- encryption strategy per biometric/media data;
- audit delle azioni.


Biometric isolation e encryption vengono introdotti prima del field pilot, non lasciati come semplice polish finale.


34. Testing
Testing layers:
- unit;
- contract;
- integration;
- replay-based perception tests;
- benchmark datasets;
- end-to-end browser phone -> Mac;
- failure/reconnect;
- privacy/retention;
- regression.


Dataset di test registrato è obbligatorio per consentire a Codex di lavorare senza accesso continuo a camera/microfono reali.


35. Observability
Metriche minime:
- FPS ingest/process;
- queue depth;
- dropped frames;
- detection latency;
- ASR latency;
- entity resolution latency;
- decision latency;
- LLM/Decision API calls;
- token/input cost;
- memory pressure;
- model load/unload;
- storage growth;
- WebRTC RTT/jitter/packet loss;
- interrupt rate;
- false identity rate.


36. Resource management M1 8 GB
Regole:
- un solo heavyweight model alla volta quando possibile;
- lazy loading;
- bounded queues;
- low-resolution perception path;
- frame sampling;
- model cache con eviction;
- batch work in idle/background;
- evitare microservizi duplicanti runtime e RAM;
- niente Redis/Kafka/NATS nell'MVP;
- memory pressure monitor;
- profilo "low-memory M1" come configurazione ufficiale.


37. Future personal server
L'architettura deve poter spostare moduli pesanti su un server personale:
- embedding;
- vision;
- LLM locale;
- consolidation;
- batch indexing.


Il Mac/phone continueranno a usare gli stessi provider contracts tramite transport locale autenticato.


38. MCP
Mnemos dovrebbe esporre in una fase successiva un MCP server per capability sicure:
- search_memory;
- get_entity;
- find_conversations;
- get_last_seen;
- create_reminder;
- list_tasks.


MCP non bypassa Policy Engine o permission model.


39. Clean uninstall
Il progetto deve fornire:
- INSTALLATION_REGISTRY.md;
- DATA_LAYOUT.md;
- scripts/doctor;
- scripts/clean-cache;
- scripts/export-data;
- scripts/purge-runtime;
- documentazione per rimuovere eventuali componenti esterni.


Una purge distruttiva deve richiedere conferma esplicita e non essere eseguita automaticamente da Codex.


40. Prima vertical slice
Definition of Product Working iniziale:
- QR pairing;
- browser phone HTTPS;
- WebRTC camera+mic;
- live dashboard;
- generic object detection;
- face detection;
- OCR;
- IT/EN ASR;
- enrollment oggetto via voce/dashboard;
- riconoscimento successivo con identity/evidence/last seen;
- enrollment persona autorizzata;
- reminder contestuale;
- Ask Tobi su memoria recente.


41. ADR iniziali obbligatori
Prima o durante l'implementazione vanno creati:
ADR-001 Modular Monolith
ADR-002 Python Core + TypeScript Web
ADR-003 Docker Infra + Native ML
ADR-004 PostgreSQL + pgvector
ADR-005 EmbeddingGemma 2
ADR-006 Object Instance Resolution
ADR-007 Browser WebRTC Sensor Gateway
ADR-008 OpenAI Cloud Providers
ADR-009 Local Decision Cascade
ADR-010 Local Media + S3 Abstraction
ADR-011 Single User Installation
ADR-012 Local-First Privacy
ADR-013 Five-Minute Rolling Buffers
ADR-014 Repository-Contained Runtime
ADR-015 Model Licensing Policy
ADR-016 HTTPS LAN Pairing


42. Criterio di evoluzione
Ogni componente più complesso viene introdotto solo se:
- un benchmark mostra bisogno reale;
- un exit criterion lo richiede;
- una limitazione concreta emerge;
- un ADR documenta il trade-off.


La priorità è una base solida, testabile, misurabile e modificabile, non massimizzare il numero di tecnologie.