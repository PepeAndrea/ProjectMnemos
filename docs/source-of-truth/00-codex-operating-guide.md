Project Mnemos
Guida Operativa per Codex


1. Scopo
Questa guida definisce come Codex deve lavorare sul progetto Project Mnemos, quali documenti costituiscono la fonte ufficiale dei requisiti, come deve essere gestito il mirror locale e come trattare eventuali divergenze tra codice e documentazione.


2. Source of Truth
La fonte ufficiale dei requisiti approvati è Google Drive, nella cartella:
Drive Personale / Progetti / Project Mnemos


Documenti canonici:
Specifica funzionale: 01 - Project Mnemos - Visione e Specifica Funzionale
Memoria, decisioni e governance: 02 - Project Mnemos - Memoria, Decisioni e Governance
Piano operativo: 03 - Project Mnemos - Piano Operativo


La numerazione dei documenti definisce l'ordine logico di lettura:
00 = guida operativa;
01 = cosa deve fare il prodotto;
02 = regole di memoria, decisione, privacy e governance;
03 = piano operativo e stato di avanzamento;
04+ = documentazione tecnica successiva, inclusi architettura, stack, API, schema dati e deployment.


3. Regola di autorità
In caso di conflitto:
1) requisiti espliciti approvati nel documento Drive più recente;
2) guida operativa;
3) piano operativo;
4) mirror locale;
5) implementazione corrente.


Il codice non diventa automaticamente la verità solo perché esiste già. Se il codice contraddice un requisito canonico, deve essere modificato oppure la divergenza deve essere segnalata come decisione architetturale da approvare.


4. Mirror locale per Codex
Nel repository deve esistere una directory dedicata, consigliata:
docs/project-mnemos/


Struttura raccomandata:
docs/project-mnemos/README.md
docs/project-mnemos/source-map.json
docs/project-mnemos/01-functional-spec.md
docs/project-mnemos/02-memory-decision-governance.md
docs/project-mnemos/03-milestones.csv
docs/project-mnemos/03-epics.csv
docs/project-mnemos/03-tasks.csv
docs/project-mnemos/04-technical-architecture.md
docs/project-mnemos/decisions/
docs/project-mnemos/changes/


Il mirror serve come input locale veloce e versionabile per Codex. Non sostituisce i documenti canonici di Drive.


5. Sync policy
Ogni snapshot locale deve contenere almeno:
- Drive file ID;
- Drive URL;
- revision/version identifier quando disponibile;
- timestamp di sincronizzazione;
- hash del file locale;
- stato: synced, local-ahead, drive-ahead o conflict.


Una modifica proposta da Codex alla specifica deve essere prima registrata nel repository come change proposal o ADR. Dopo approvazione viene riportata nel documento Drive canonico e quindi il mirror viene rigenerato. Codex non deve modificare silenziosamente i requisiti per adattarli all'implementazione.


6. Processo di lavoro Codex
Prima di implementare un epic:
- leggere 00, 01 e 02;
- leggere milestone, epic e task rilevanti nel piano operativo;
- verificare dipendenze e acceptance criteria;
- controllare le ADR già approvate;
- identificare eventuali decisioni ancora aperte.


Durante l'implementazione:
- mantenere separati perception, entity resolution, memory, decision, reasoning e action;
- evitare dipendenze cloud non previste;
- rispettare local-first e data minimization;
- aggiungere test automatici per ogni comportamento critico;
- mantenere osservabilità di latenza, costi, storage e confidence.


Al completamento:
- eseguire test;
- aggiornare lo stato dei task;
- aggiungere note tecniche e decisioni;
- indicare chiaramente limitazioni o feature parziali;
- non dichiarare un milestone completo finché gli exit criteria non sono verificati.


7. Definition of Done
Una feature è Done solo quando:
- implementazione completata;
- test automatici passano;
- comportamento verificato sul caso d'uso target;
- telemetria minima disponibile;
- privacy/retention rispettate;
- failure mode principali gestiti;
- documentazione tecnica aggiornata;
- task nel piano operativo aggiornato.


8. Decision Records
Le decisioni architetturali rilevanti devono essere registrate come ADR, per esempio:
ADR-001 scelta linguaggio/backend;
ADR-002 storage e vector search;
ADR-003 protocollo smartphone-computer;
ADR-004 local LLM vs cloud;
ADR-005 modelli perception;
ADR-006 strategia event bus;
ADR-007 schema memory consolidation.


Ogni ADR deve contenere problema, opzioni considerate, decisione, motivazione, conseguenze e possibilità di revisione.


9. Regola sui requisiti mancanti
Se un requisito è ambiguo ma può essere risolto con una scelta interna reversibile, Codex può scegliere l'opzione più semplice e documentarla. Se la scelta influenza privacy, sicurezza, dati biometrici, compatibilità hardware, vendor lock-in, costi ricorrenti o architettura fondamentale, deve essere trattata come decisione esplicita e non nascosta nell'implementazione.


10. Remote Mobile Sensor
Il telefono deve essere supportato come sensore remoto prima del wearable definitivo. Deve poter inviare camera e microfono al computer, che rimane il local brain. La scelta del protocollo è una decisione architetturale da documentare; WebRTC è un candidato, non ancora una decisione definitiva.


La prima implementazione deve privilegiare:
- bassa latenza;
- semplicità di pairing;
- rete locale;
- audio/video sincronizzati;
- riconnessione;
- autenticazione;
- telemetria;
- possibilità di estensione futura via Internet.


11. Obiettivo finale per Codex
Codex riceverà come goal il completamento incrementale del prodotto fino al raggiungimento degli exit criteria concordati. Non deve produrre solo scaffolding o demo isolate: ogni milestone deve lasciare una parte del sistema realmente utilizzabile e testabile.


12. Documentazione tecnica futura
La documentazione successiva dovrà coprire almeno:
- architettura logica;
- architettura di runtime;
- stack tecnologico;
- modelli ML/AI;
- hardware target;
- protocolli;
- schema database;
- API contracts;
- event model;
- security model;
- deployment locale/cloud;
- mobile client;
- testing strategy;
- observability;
- performance budgets;
- cost budgets
13. Nome dell'assistente e interazione
L'assistente conversazionale del progetto si chiama Tobi. Il nome deve essere scritto sempre con la i finale. Tobi non è un semplice wake-word assistant: il sistema resta percettivamente attivo secondo le policy definite, distingue conversazioni ambientali da richieste rivolte all'assistente e aumenta la confidence di intent quando il nome Tobi viene pronunciato esplicitamente.


14. Bootstrap del repository
Il repository deve contenere due file operativi alla radice:
AGENTS.md: istruzione breve e autoritativa che obbliga Codex a leggere CODEX.md e la source of truth prima di intervenire.
CODEX.md: guida completa di esecuzione autonoma del progetto.


La copia locale dei documenti canonici vive in docs/source-of-truth ed è una cache versionabile. Non può prevalere sui documenti Google Drive. Il file docs/source-of-truth/manifest.json deve registrare per ogni fonte ID Drive, URL canonico, revisione o timestamp, path locale, data sync e checksum.


15. Ciclo autonomo di Codex
Codex deve lavorare per milestone, epic e task rispettando le dipendenze. Per ogni task:
- legge requisiti, dipendenze, ADR e acceptance criteria;
- implementa la soluzione più semplice compatibile con l'architettura;
- aggiunge o aggiorna test;
- esegue lint, typecheck, test e benchmark applicabili;
- corregge regressioni prima di procedere;
- aggiorna documentazione tecnica e registry quando necessario;
- marca Done solo dopo verifica oggettiva.


Una Epic è Done solo quando tutti i task applicabili sono Done e il risultato integrato soddisfa il comportamento previsto.
Una Milestone è Done solo quando gli exit criteria documentati sono verificati end-to-end, non soltanto quando i task risultano chiusi.
Codex continua autonomamente col successivo lavoro sbloccato finché esistono task realizzabili. Un dubbio tecnico reversibile deve essere risolto tramite benchmark, ADR o scelta conservativa; non deve bloccare l'intero progetto. Si ferma solo su un blocco reale che richiede informazione esterna o una decisione irreversibile non coperta dalla source of truth.


16. Contenimento dell'ambiente locale
Il progetto deve essere disinstallabile e ripulibile in modo prevedibile. Dati, modelli, media, cache applicative, log, file temporanei, database bind-mounted e dataset devono essere collocati sotto la directory del repository, salvo componenti di sistema inevitabili.


INSTALLATION_REGISTRY.md deve registrare ogni dipendenza o installazione significativa con versione, scopo, metodo d'installazione, posizione, dimensione stimata, necessità e procedura di rimozione.
DATA_LAYOUT.md deve documentare ogni directory persistente, tipo di dato, retention e strategia di cancellazione.
Le cache di Hugging Face, modelli, runtime AI e tool devono essere reindirizzate sotto runtime/cache o runtime/models quando tecnicamente possibile.


17. Modello di autonomia
Il target finale è un repository che Codex possa portare avanti senza prompt operativi continui. Il prompt umano può limitarsi a ordinare di seguire AGENTS.md e CODEX.md e continuare fino al completamento dei task realizzabili. La qualità, la correttezza, la tracciabilità e la riproducibilità prevalgono sulla velocità di consegna.
.