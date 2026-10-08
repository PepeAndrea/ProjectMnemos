Project Mnemos
Memoria, Decisioni e Governance


1. Scopo del documento
Questo documento descrive le regole concettuali con cui Project Mnemos trasforma flussi sensoriali continui in informazioni persistenti, decide quando coinvolgere modelli intelligenti, limita la registrazione dei dati e governa le azioni. Non definisce ancora lo stack tecnologico definitivo: le scelte di librerie, framework, database e modelli saranno trattate separatamente.


2. Pipeline cognitiva
La pipeline logica è:
SENSORS -> PERCEPTION -> OBSERVATIONS -> EVENTS -> WORLD STATE -> ATTENTION/DECISION -> MEMORY/REASONING -> ACTION.


Il sistema deve impedire che il flusso sensoriale grezzo arrivi direttamente ai modelli generativi. Ogni passaggio deve ridurre volume, aumentare struttura e conservare la provenienza.


3. Osservazioni
Una Observation rappresenta ciò che il sistema ritiene di aver percepito in uno specifico istante. Esempi:
- una persona è apparsa nel frame;
- un oggetto noto è visibile;
- un nuovo testo OCR è stato letto;
- una voce ha pronunciato una frase;
- un oggetto non è più visibile;
- una macchina presenta una differenza visiva.


Campi concettuali:
- observation_id;
- timestamp;
- sensor/source;
- modality;
- entity candidates;
- confidence;
- spatial context;
- evidence references;
- track/session ID;
- raw-buffer references temporanee.


4. Eventi
Le observations non vengono tutte persistite come memoria. L'Event Aggregator unisce observations temporalmente e semanticamente correlate in eventi.


Esempi:
- "Marco è entrato nella stanza";
- "Andrea ha spostato le chiavi dalla cucina alla scrivania";
- "È iniziata una conversazione con Marco";
- "È stato pronunciato un commitment";
- "La macchina M01 mostra una variazione nella zona posteriore".


Un evento deve poter contenere provenance sufficiente per ricostruire il perché della sua creazione.


5. World State e Hot Memory
La Hot Memory è lo stato operativo corrente, con durata breve. Può contenere:
- current user;
- current people;
- current visual entities;
- current speakers;
- current conversation;
- current topic;
- current focus object;
- current location;
- recent utterances;
- recent events;
- active reminders;
- active tasks;
- pending confirmations.


Questa memoria è ottimizzata per risolvere riferimenti linguistici come "lui", "questo", "quello", "quando lo rivedo" e per dare al decision layer un contesto compatto.


6. Long-Term Memory
La memoria a lungo termine non è un dump dello stream. Contiene elementi consolidati:
- entities;
- relationships;
- semantic facts;
- episodes;
- conversations;
- utterances selezionate;
- tasks;
- reminders;
- commitments;
- decisions;
- observations rilevanti;
- embeddings;
- evidence metadata.


Ogni ricordo deve avere una provenance e, ove possibile, un livello di confidenza.


7. Memoria semantica
Rappresenta fatti relativamente stabili.


Esempi:
- Marco lavora sul progetto X;
- il MacBook M01 appartiene ad Andrea;
- la macchina M01 si trova normalmente nel laboratorio;
- questa borsa viene chiamata "zaino lavoro".


I fatti devono poter essere aggiornati, contraddetti, versionati o marcati come incerti. Un LLM non deve trasformare automaticamente una singola frase casuale in verità permanente senza un livello di confidenza e una policy.


8. Memoria episodica
Rappresenta un accadimento specifico:
- chi;
- cosa;
- quando;
- dove;
- contesto;
- sorgenti;
- eventuale audio/keyframe;
- entità coinvolte.


La memoria episodica è il fondamento per domande temporali e narrative.


9. Memoria prospettica
Rappresenta qualcosa che deve accadere in futuro quando si verifica una condizione.


Tipi di trigger:
- tempo/data;
- person seen;
- object seen;
- location entered;
- conversation with entity;
- topic detected;
- device state;
- combined condition.


Esempio:
trigger = Marco visible;
condition = work context;
action = remind "chiedi dell'autenticazione API".


10. Consolidamento
Le informazioni devono poter essere consolidate periodicamente.


Esempio:
dieci observations di uno stesso oggetto nella stessa posizione non devono produrre dieci memorie indipendenti. Possono diventare:
"AirPods osservate sulla scrivania tra le 13:04 e le 13:32; ultima osservazione affidabile 13:32".


Una conversazione di 45 minuti può produrre:
- transcript;
- summary;
- 4 decisions;
- 3 tasks;
- 2 commitments;
- 5 memory updates.


11. Forgetting e decay
La memoria deve poter dimenticare. Possibili regole:
- scadenza temporale;
- decay di importanza;
- deduplicazione;
- consolidamento;
- cancellazione esplicita;
- retention per categoria;
- retention per persona;
- retention per device/sensore.


Il sistema deve evitare l'accumulo infinito di dati di basso valore.


12. Audio retention
Default consigliato:
- microfono continuamente disponibile solo al perception loop;
- rolling buffer breve;
- VAD per individuare parlato;
- audio irrilevante sovrascritto;
- transcript temporaneo per classificazione;
- persistenza solo in sessioni/eventi selezionati.


Modalità:
Privacy: niente audio persistente.
Standard: transcript/memory strutturata, audio non persistente salvo comando.
Enhanced: clip associate ad eventi selezionati.
Meeting: registrazione della sessione esplicitamente attivata.
Evidence: clip audio/video specifica associata a un evento.


13. Video retention
Default:
- stream elaborato in realtime;
- nessun archivio video continuo;
- rolling buffer breve;
- keyframe per eventi rilevanti;
- clip solo quando una policy lo giustifica.


L'obiettivo è poter ricordare "cosa è successo" senza dover conservare "tutto quello che è successo".


14. LLM budget
L'LLM non deve essere invocato per ogni frame né per ogni utterance.


Strategia:
- Level 0 filtra deterministicamente;
- Level 1 classifica relevance/intent/action;
- Level 2 viene invocato solo per ambiguità, reasoning, sintesi, query e pianificazione.


Il sistema deve aggregare il parlato prima di invocare un modello grande. Una conversazione deve generare poche elaborazioni significative, non una chiamata per frase.


15. Decision contract
Il System 1 deve operare su azioni bounded e codificate.


Esempio di action set:
- DO_NOTHING;
- STORE_OBSERVATION;
- UPDATE_ENTITY;
- CREATE_MEMORY_CANDIDATE;
- NOTIFY;
- ASK_USER;
- QUERY_MEMORY;
- INSPECT_DEEPER;
- CALL_LLM;
- CREATE_TASK_CANDIDATE;
- CREATE_REMINDER_CANDIDATE.


Il decision model non deve inventare tool o permessi.


16. Interruptibility
Uno dei problemi principali di un wearable cognitivo è evitare notifiche inutili.


Ogni potenziale interrupt deve avere almeno:
- relevance score;
- urgency;
- confidence;
- current user activity;
- interruption cost;
- cooldown;
- duplicazione con notifiche recenti.


L'obiettivo è minimizzare il numero di interruzioni che l'utente considera inutili.


17. Confidence management
Le identità e le memorie non devono essere binarie quando il segnale è incerto.


Esempi:
- recognized = high confidence;
- candidate = medium confidence;
- unknown = low confidence;
- conflict = più candidati compatibili;
- needs_confirmation = necessario input dell'utente.


Le soglie saranno calibrate successivamente per dominio.


18. Evidence Engine
Ogni decisione di riconoscimento deve poter puntare alle sue evidenze.


Per oggetti:
- class detector;
- visual embedding score;
- local feature matches;
- OCR;
- color/shape attributes;
- historical location;
- co-occurrence.


Per persone:
- face embedding;
- voice embedding;
- track continuity;
- multimodal consistency.


Per conversazioni:
- original utterance;
- timestamp;
- speaker assignment;
- transcript confidence;
- audio segment reference.


19. LLM explainability
L'LLM può spiegare le evidenze ma non deve crearle.


Pattern corretto:
Evidence Engine -> structured evidence -> LLM explanation.


Pattern scorretto:
Image -> LLM inventa liberamente il motivo per cui l'entità è stata identificata.


20. Action governance
Ogni azione deve avere:
- action type;
- requested by;
- source event;
- parameters;
- confidence;
- risk level;
- confirmation policy;
- execution result;
- audit trail.


Esempi di policy:
CREATE_MEMORY: automatico.
CREATE_INTERNAL_TASK: automatico o configurable.
DRAFT_EMAIL: automatico.
SEND_EMAIL: conferma.
UPDATE_CRM: automatico solo per campi a basso rischio o configurabile.
CREATE_CALENDAR_EVENT: conferma.
DELETE: conferma forte.
PURCHASE/PAYMENT: fuori scope iniziale o conferma forte.


21. User corrections
Le correzioni dell'utente sono segnali di alta qualità.


Esempi:
- "Non è Marco, è Luca";
- "Questa non è la mia borsa";
- "Non ricordare questa conversazione";
- "Quando dico progetto X intendo Y";
- "Questa persona si chiama ...".


Le correzioni devono aggiornare entity resolution, facts o policy senza richiedere necessariamente retraining immediato.


22. Enrichment controllato
Un'entità può essere arricchita con informazioni esterne soltanto se:
- l'utente lo richiede;
- una integrazione autorizzata lo fornisce;
- la provenance è mantenuta;
- la policy consente la fusione.


Non bisogna confondere una supposizione del modello con un attributo verificato.


23. Privacy by design
Principi:
- minimizzazione dei dati;
- local-first;
- encryption at rest e in transit;
- controllo per categoria di dati;
- retention configurabile;
- cancellazione;
- audit;
- separazione identità/sessione;
- opt-in per riconoscimento biometrico;
- modalità chiara di registrazione conversazioni;
- indicatori visibili/udibili quando opportuno;
- possibilità di sospendere rapidamente sensori e memoria.


24. Persone non registrate
Una persona non registrata può avere solo un'identità effimera, per esempio Unknown Session Person #12, sufficiente a mantenere continuità all'interno della sessione. Il sistema non deve trasformarla automaticamente in identità persistente.


25. Dati biometrici
Face embeddings e voice embeddings devono essere trattati come dati ad alta sensibilità. Devono avere:
- storage separabile;
- encryption;
- access control;
- enrollment esplicito;
- possibilità di revoca;
- cancellazione effettiva;
- logging accessi.


26. Conversazioni
Per ogni sessione va distinto:
- percepire temporaneamente il parlato per capire comandi;
- conservare una trascrizione;
- conservare l'audio;
- identificare persistentemente gli speaker.


Sono quattro livelli differenti di trattamento e devono avere policy indipendenti.


27. Audit e provenance
Ogni memoria o azione importante deve poter rispondere:
- da dove arriva?;
- quando è stata creata?;
- con quale confidenza?;
- quale modello/regola l'ha generata?;
- quali evidenze aveva?;
- è stata confermata dall'utente?;
- è stata modificata successivamente?


28. Failure modes da progettare
- falso riconoscimento di una persona;
- oggetti simili confusi;
- diarizzazione errata;
- ASR errato;
- pronome risolto sulla persona sbagliata;
- reminder attivato nel contesto sbagliato;
- eccesso di notifiche;
- task creati da frasi non impegnative;
- salvataggio di informazioni non importanti;
- mancato salvataggio di un evento importante;
- perdita del device;
- compromissione del database;
- indisponibilità del cloud;
- sensori offline.


29. Offline-first behavior
Quando il cloud è assente il sistema dovrebbe mantenere:
- perception locale;
- tracking;
- memoria locale;
- query semplici;
- reminder;
- queue delle elaborazioni che richiedono cloud.


Le feature che necessitano di modelli remoti possono degradare in modo controllato.


30. Cost control
Metriche:
- LLM calls/day;
- tokens/day;
- System 1 decisions/hour;
- storage/day;
- average audio persisted/day;
- keyframes/day;
- cloud vision requests/day;
- percentage local inference.


Devono essere osservabili fin dall'MVP per evitare che il prodotto diventi costoso solo dopo l'introduzione del wearable.


31. Sicurezza delle azioni
Un prompt o una frase ascoltata da terzi non deve automaticamente diventare un comando privilegiato. È necessario distinguere:
- command owner;
- speaker identity;
- wake/command mode;
- confirmation level;
- tool permission.


Il sistema deve resistere a comandi pronunciati da persone diverse dall'utente.


32. Priorità di implementazione
Prima validare:
- percezione;
- entity resolution;
- observations;
- last seen;
- audio transcription;
- conversations;
- memory query;
- task/reminder extraction.


Poi:
- decision models;
- prospective memory;
- action engine;
- integrations;
- wearable.


33. Decisioni ancora aperte
- modello di identity graph;
- policy di consolidation;
- durata rolling buffer;
- criteri di evento significativo;
- strategia hot memory;
- soglie di confidence;
- modello System 1;
- modello LLM locale/remoto;
- livello di on-device inference;
- policy di registrazione conversazioni;
- schema di encryption e key management;
- modalità di wearable output;
- strategia di sync multi-device.


34. Definizione di successo del core
Il core è validato quando, senza smart glasses proprietari, riesce a:
- riconoscere e ricordare entità;
- rispondere a last-seen;
- ricostruire conversazioni;
- creare memorie affidabili;
- risolvere query temporali e semantiche;
- estrarre task e commitments;
- attivare reminder contestuali;
- motivare i riconoscimenti con evidenze;
- mantenere costi e storage limitati;
- funzionare localmente per la maggior parte del tempo.


35. Visione di lungo periodo
Il sistema deve essere visto come un Personal World Model controllato dall'utente. Sensori differenti alimentano lo stesso modello del mondo; agenti e strumenti differenti utilizzano la stessa memoria. La qualità del prodotto dipenderà meno dalla quantità di dati raccolti e più dalla capacità di selezionare, collegare, dimenticare, recuperare e usare correttamente l'informazione
36. Unified Multimodal Embedding Layer
EmbeddingGemma 2 è il candidato primario per lo spazio vettoriale multimodale di Mnemos. Deve essere valutato per testo, OCR, immagini/keyframe, crop di oggetti, segmenti audio e momenti video. L'obiettivo è consentire retrieval cross-modale: una query testuale può recuperare evidenze visive o audio e viceversa.


La dimensionalità di default non viene fissata senza benchmark. Codex deve confrontare almeno 256, 512 e 768 dimensioni valutando recall, precisione, RAM, latenza, dimensione indice e throughput sul MacBook M1 8 GB. pgvector resta il backend vettoriale iniziale.


EmbeddingGemma 2 non è sufficiente, da solo, a provare l'identità fisica di un oggetto. Per distinguere due istanze semanticamente simili il resolver deve poter combinare embedding multimodale con feature locali, OCR, attributi, continuità del tracking e contesto storico.


37. Decision Routing locale e cloud
Il decision layer segue una cascata:
- regole e soglie deterministiche;
- routing semantico locale leggero, incluso EmbeddingGemma 2 quando il benchmark lo giustifica;
- OpenAI Decisions API come decision model cloud principale;
- LLM generativo soltanto quando serve estrazione strutturata complessa, reasoning, spiegazione o pianificazione.


Il cloud decision layer riceve solo rappresentazioni necessarie al compito. L'audio non deve essere inviato direttamente a un endpoint che non lo supporta: viene prima trasformato localmente in transcript/event state. Decisioni che producono effetti privilegiati passano sempre dal Policy Engine indipendentemente dal modello che le propone.


38. Speaker ownership e comandi
La voce dell'utente principale deve poter essere enrolldata. Un comando con effetti sul sistema deve includere speaker attribution e confidence. Una voce diversa dall'utente non può ottenere automaticamente privilegi operativi. Il contenuto di terzi può generare memoria o candidate task solo in base alle policy della conversazione.


39. Retention conversazionale
Fuori dalla modalità Recording/Meeting il sistema non conserva automaticamente registrazioni complete. Mantiene il rolling buffer fino a cinque minuti, trascrizioni/eventi temporanei e rende persistenti soltanto memorie, utterance o clip giudicate utili dalle policy. Quando l'utente attiva esplicitamente la registrazione, l'audio della sessione viene conservato fino allo stop e rimane collegato a transcript e timecode.


40. Local-first e fallback
Il sistema deve restare utile senza LLM locale e senza cloud continuo. Sul MacBook M1 8 GB il core deve privilegiare modelli piccoli, caricamento lazy e pipeline event-driven. Se in futuro è disponibile un personal server più potente, provider locali aggiuntivi possono essere attivati senza modificare i contratti di dominio.
.