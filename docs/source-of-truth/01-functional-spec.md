Project Mnemos
Visione e Specifica Funzionale


1. Sintesi del progetto
Project Mnemos è un sistema cognitivo multimodale personale progettato per percepire il mondo reale tramite camera, microfono e altri sensori, trasformare ciò che accade in entità, eventi, ricordi e intenzioni interrogabili, decidere cosa merita attenzione e collegare il contesto fisico alle azioni digitali. Gli smart glasses sono uno dei possibili sensori, non il prodotto in sé: il core deve poter ricevere input anche da smartphone, webcam, computer, telecamere, dispositivi edge e futuri wearable.


L'obiettivo è costruire una memoria persistente del contesto reale capace di rispondere a domande come: "Dove ho lasciato le chiavi?", "Cosa mi aveva detto Marco sull'API?", "Quando rivedo questa persona ricordami di chiederle una cosa", "Che oggetto è questo?", "È lo stesso oggetto visto ieri?", "Cosa è cambiato rispetto all'ultima volta?", "Quali impegni ho preso in questa conversazione?" e, quando autorizzato, eseguire o preparare azioni sui sistemi digitali.


2. Principi di prodotto
Il sistema deve essere local-first: la percezione continua, il filtraggio, il tracking e la maggior parte delle operazioni frequenti devono avvenire localmente o sull'edge. Il cloud deve essere usato come fallback per reasoning complesso, modelli più pesanti o integrazioni che lo richiedono.


Il sistema non deve registrare indiscriminatamente tutto. Deve applicare una compressione cognitiva progressiva: il mondo produce un flusso continuo, il perception layer lo converte in osservazioni, l'event layer seleziona i cambiamenti significativi, il decision layer valuta rilevanza e priorità, la memoria conserva solo ciò che è utile.


Il sistema deve separare chiaramente percezione, identità, memoria, decisione, ragionamento e azione. Un LLM non deve decidere se un volto corrisponde a una persona nota, né inventare evidenze visive. Le decisioni deterministiche o probabilistiche a bassa latenza devono essere gestite da componenti dedicati.


3. Modalità di acquisizione
Input visivi:
- camera di smart glasses;
- camera smartphone;
- webcam;
- stream RTSP o telecamere autorizzate;
- immagini singole;
- screenshot o feed dello schermo, in futuro.


Input audio:
- microfono smart glasses;
- microfono smartphone;
- microfono computer;
- registrazione meeting esplicita;
- audio proveniente da altri device autorizzati.


Input contestuali futuri:
- posizione;
- IMU e movimento;
- calendario;
- email;
- CRM;
- documenti;
- notifiche;
- dispositivi IoT;
- stato del computer.


4. Perception visiva
Il layer visivo deve gestire:
- object detection generica;
- riconoscimento di oggetti specifici già registrati;
- face detection;
- face recognition per persone consenzienti e registrate;
- tracking persistente degli oggetti e delle persone tra frame;
- OCR di testi, etichette, documenti, schermi e insegne;
- visual embeddings per confronto semantico;
- local feature matching per distinguere oggetti simili tramite dettagli specifici;
- identificazione di anomalie o cambiamenti rispetto a osservazioni precedenti;
- stima della qualità del riconoscimento;
- raccolta di evidenze del perché una determinata entità è stata associata a un oggetto visto.


5. Entity Resolution
Ogni elemento osservato deve poter diventare un'entità persistente. Le entità non sono limitate agli oggetti ma comprendono:
- persone;
- oggetti personali;
- dispositivi;
- veicoli;
- documenti;
- prodotti;
- luoghi;
- macchinari;
- componenti;
- animali;
- concetti o elementi digitali quando associabili al mondo reale.


Ogni entità può avere:
- ID univoco;
- tipo;
- nome umano;
- alias;
- immagini di riferimento;
- embeddings visivi;
- embeddings vocali ove appropriato;
- attributi;
- relazioni;
- proprietà;
- storico delle osservazioni;
- ultima posizione o contesto noto;
- livello di confidenza;
- provenienza delle informazioni;
- policy di retention.


6. Riconoscimento di oggetti specifici
Il sistema deve poter essere istruito con frasi come "Memorizza questo come il mio zaino". Non è necessario addestrare un nuovo detector per ogni oggetto. Il flusso previsto è:
1. il detector identifica la classe generale;
2. viene estratta la regione dell'oggetto;
3. si calcola un embedding visuale;
4. si effettua una ricerca tra le entità note;
5. si confrontano, se necessario, feature locali, OCR e attributi;
6. il sistema restituisce una confidence e un insieme di evidenze.


Le evidenze possono includere similitudine embedding, logo, testo OCR, colore, forma, dettagli locali, graffi, adesivi, componenti, contesto storico e coerenza con l'ambiente.


7. Persone, volti e voce
Per le persone registrate il sistema può mantenere una Identity Entity con:
- face embeddings;
- voice embeddings;
- immagini autorizzate;
- relazione con l'utente;
- contesto professionale o personale;
- cronologia delle interazioni;
- conversazioni associate;
- task e impegni collegati.


Le persone non registrate devono rimanere anonime o avere un'identità temporanea/sessione con retention limitata. Il sistema deve distinguere chiaramente tra tracking temporaneo e identificazione persistente.


8. Perception audio
L'audio non deve essere trattato come mera registrazione. La pipeline deve comprendere:
- Voice Activity Detection;
- riduzione rumore;
- speech-to-text realtime;
- diarizzazione;
- speaker recognition per voci autorizzate;
- segmentazione della conversazione;
- timestamp di ogni utterance;
- classificazione preliminare di intenti ed eventi;
- correlazione con il contesto visivo.


L'obiettivo è passare da "audio grezzo" a una sequenza di eventi linguisticamente e semanticamente strutturati.


9. Conversazioni
Una conversazione è un'entità di primo livello e può contenere:
- data e ora;
- luogo o contesto;
- partecipanti;
- transcript;
- segmenti audio originali;
- topic;
- riepilogo;
- decisioni;
- task;
- impegni;
- richieste;
- domande aperte;
- entità citate;
- documenti o oggetti coinvolti.


Il sistema deve permettere query come:
- "Cosa mi disse Marco oggi sull'API?";
- "Quando abbiamo deciso questa cosa?";
- "Fammi risentire il pezzo in cui ne abbiamo parlato";
- "Quali cose ho promesso a questa persona?";
- "Quali decisioni sono uscite dall'ultimo incontro?".


Quando l'audio originale è stato conservato, il sistema deve poter riprodurre esattamente il segmento sorgente collegato al ricordo.


10. Intent e linguaggio
Ogni frase rilevante può essere classificata in categorie come:
- question;
- command;
- task;
- reminder;
- contextual reminder;
- memory;
- fact;
- commitment;
- entity update;
- entity enrollment;
- entity search;
- action request;
- scheduling intent;
- casual conversation;
- ignore.


Il parsing deve produrre strutture eseguibili e non solo testo. Esempio: "Quando rivedo Marco ricordami di chiedergli dell'autenticazione" deve diventare un trigger basato sull'apparizione dell'entità Marco e un'azione di notifica.


11. Memoria
Il sistema deve implementare almeno tre tipi di memoria.


Memoria semantica:
fatti relativamente stabili come "Marco è Tech Lead del progetto X" o "questo MacBook appartiene ad Andrea".


Memoria episodica:
eventi con data, luogo, partecipanti, evidenze e sorgente, ad esempio "Il 7 ottobre Marco ha detto X durante una conversazione in ufficio".


Memoria prospettica:
intenzioni future che si attivano quando una condizione si verifica, ad esempio "quando vedo Marco ricordami di chiedergli dell'API".


È utile inoltre distinguere una hot memory di breve periodo, che descrive il contesto attuale, da una long-term memory consolidata.


12. World Model
Il sistema deve mantenere uno stato corrente del mondo contenente, quando disponibili:
- utente corrente;
- posizione;
- persone vicine;
- oggetti visibili;
- oggetto/focus corrente;
- attività in corso;
- conversazione corrente;
- topic corrente;
- task aperti;
- intenzioni pendenti;
- entità rilevanti;
- eventi recenti.


Questo stato intermedio permette di disaccoppiare i sensori dai modelli decisionali e dai modelli generativi.


13. Decision Layer
Il sistema usa una gerarchia a tre livelli.


Level 0 - Reflex:
regole, tracking, soglie e logica deterministica. Esempi: oggetto entrato nel frame, volto perso, testo comparso, trigger temporale.


Level 1 - System 1:
decisioni rapide e bounded. Esempi:
- è rilevante?;
- è anomalo?;
- vale la pena memorizzarlo?;
- devo interrompere l'utente?;
- quale azione tra quelle consentite è più appropriata?;
- serve escalation al reasoning?;
- questa situazione attiva un'intenzione futura?


Level 2 - System 2 / LLM:
ragionamento aperto, risoluzione delle ambiguità, sintesi, spiegazione, pianificazione, collegamento con conoscenza storica e conversazione naturale.


14. Ruolo dell'LLM
L'LLM deve essere invocato in modo event-driven, non frame-driven e non necessariamente per ogni frase. I suoi compiti principali:
- risolvere pronomi e riferimenti usando il contesto;
- trasformare linguaggio naturale in strutture;
- sintetizzare conversazioni;
- estrarre decisioni, task e commitments;
- mettere in relazione eventi con memoria storica;
- rispondere a query;
- formulare spiegazioni;
- costruire piani;
- preparare azioni complesse;
- interrogare strumenti e sistemi esterni quando autorizzato.


15. Action Engine
Le azioni possibili comprendono:
- creare memoria;
- aggiornare un'entità;
- creare task;
- creare reminder;
- creare reminder contestuale;
- preparare email o messaggi;
- aggiornare CRM;
- creare note;
- preparare eventi calendario;
- eseguire query;
- avviare registrazioni esplicite;
- riprodurre un segmento audio;
- notificare l'utente;
- richiedere conferma;
- chiamare un LLM o un altro agente.


Il sistema deve avere un Policy Engine separato dall'LLM. Operazioni a basso rischio possono essere automatiche; operazioni esterne o distruttive devono richiedere livelli di conferma coerenti col rischio.


16. Retrieval e ricerca
Project Mnemos deve diventare un "Ctrl+F del mondo reale". La ricerca deve essere possibile per:
- entità;
- persona;
- tempo;
- luogo;
- topic;
- testo pronunciato;
- testo OCR;
- somiglianza visiva;
- eventi;
- conversazioni;
- task;
- decisioni;
- commitments.


Esempio: "Dove sono le AirPods?" interroga l'ultima osservazione affidabile dell'entità AirPods e risponde con luogo, tempo e confidenza.


17. Evidenze ed explainability
Ogni riconoscimento rilevante deve poter conservare le evidenze del matching. Le spiegazioni in linguaggio naturale devono essere generate a partire da tali evidenze, non inventate dal modello generativo.


Un riconoscimento può essere sostenuto da:
- confidence detector;
- similarity embedding;
- local feature matches;
- OCR;
- attributi;
- posizione;
- coerenza temporale;
- associazioni storiche;
- tracker ID.


18. Storage e retention
Il sistema non deve conservare normalmente il video grezzo continuo. Strategia di default:
- video: elaborazione realtime, nessuna retention continua;
- rolling video buffer: breve e sovrascritto;
- audio: rolling buffer breve;
- transcript: persistente solo per sessioni/eventi rilevanti;
- keyframe: event-driven;
- clip: conservate solo per eventi, meeting o modalità esplicite;
- embeddings e osservazioni: persistenti secondo policy;
- registrazione completa meeting: solo quando attivata.


Sono previste modalità come Privacy, Standard, Enhanced, Meeting ed Evidence.


19. Compressione cognitiva
Una giornata di esperienza deve essere progressivamente compressa:
flusso sensoriale -> osservazioni -> eventi -> eventi significativi -> memorie -> task/intenzioni.
La metrica importante non è conservare tutto, ma massimizzare il rapporto tra esperienza e informazione realmente utile.


20. Smart glasses ed edge
Gli smart glasses sono principalmente sensori e interfaccia. Il calcolo può essere distribuito:
- glasses: camera, microfono, IMU, output audio/display;
- smartphone: decoding, frame sampling, tracking, inferenza leggera, buffering;
- local brain: PC/Mac/edge server per modelli più pesanti, database e memoria;
- cloud: reasoning, fallback o integrazioni selettive.


Il sistema deve poter funzionare inizialmente senza occhiali usando webcam e microfono, così da validare il core prima dell'hardware wearable.


21. Casi d'uso personali
- ricordare dove sono stati lasciati oggetti;
- ricordare chi è una persona e il contesto associato;
- richiamare una conversazione;
- riascoltare un passaggio;
- ricordare promesse fatte;
- creare reminder contestuali;
- identificare oggetti;
- spiegare ciò che si sta guardando;
- cercare informazioni nel proprio storico;
- riconoscere un oggetto personale specifico;
- ricevere suggerimenti in base al contesto;
- trasformare frasi spontanee in task.


22. Casi d'uso lavoro
- riconoscere interlocutori e recuperare il contesto CRM;
- ricordare follow-up aperti quando si incontra una persona;
- generare note meeting;
- aggiornare automaticamente record e task;
- estrarre richieste commerciali;
- identificare commitment;
- associare documenti e schermi a progetti;
- creare una memoria operativa delle conversazioni;
- preparare azioni successive alla fine di un incontro.


23. Casi d'uso industriali
- riconoscere macchinari e componenti;
- confrontare lo stato attuale con precedenti osservazioni;
- individuare anomalie;
- recuperare procedure;
- registrare interventi;
- creare task di manutenzione contestuali;
- associare una segnalazione vocale a un componente visibile;
- conservare evidenza fotografica del problema.


24. Casi d'uso accessibility
- descrivere scene;
- leggere testi;
- riconoscere persone autorizzate;
- individuare oggetti;
- supportare orientamento e ricerca;
- notificare cambiamenti rilevanti nell'ambiente.


25. Casi d'uso home e IoT
- ricerca oggetti;
- memoria di eventi domestici;
- trigger basati su persone, stanze o oggetti;
- interazioni con dispositivi autorizzati;
- storico contestuale di asset e ambienti.


26. Query esemplificative
- "Dove ho messo le chiavi?"
- "Chi è questa persona?"
- "Quando l'ho vista l'ultima volta?"
- "Cosa mi disse Marco ieri?"
- "Fammi risentire il pezzo."
- "Quali cose ho promesso questa settimana?"
- "Ricordami questa cosa quando lo rivedo."
- "Memorizza questo come il mio zaino."
- "Cosa è cambiato su questa macchina?"
- "Che task sono usciti da questa conversazione?"
- "Cerca tutte le volte in cui abbiamo parlato di autenticazione."
- "Qual è l'ultima posizione nota delle AirPods?"
- "Preparami il follow-up per la persona con cui ho appena parlato."


27. Non-obiettivi iniziali
- registrare e conservare indiscriminatamente tutta la giornata;
- identificare persistentemente persone non consenzienti;
- dare al modello generativo potere arbitrario sugli strumenti;
- dipendere dal cloud per ogni inferenza;
- addestrare un modello custom per ogni oggetto;
- costruire subito hardware proprietario;
- progettare subito un prodotto consumer finale prima di validare il core.


28. MVP proposto
L'MVP deve funzionare con webcam e microfono su un computer.


MVP 0 - Perception:
object detection, tracking, OCR, face detection, ASR e visualizzazione eventi.


MVP 1 - Entity Memory:
registrazione di oggetti e persone autorizzate, embeddings, entity resolution, observations, last seen e ricerca.


MVP 2 - Audio Memory:
trascrizione, diarizzazione, conversations, utterances, ricerca e segmenti audio.


MVP 3 - Cognitive Layer:
System 1 per routing e rilevanza, LLM per estrazione e query, hot memory e long-term memory.


MVP 4 - Prospective Memory:
task, reminder temporali e reminder basati sul contesto reale.


MVP 5 - Action Engine:
integrazione con strumenti digitali e policy di conferma.


MVP 6 - Wearable:
smart glasses -> smartphone -> local brain.


29. Metriche di successo
- precisione entity resolution;
- false positive rate per persone e oggetti;
- latenza detection -> decisione;
- latenza query -> risposta;
- numero di eventi generati per ora;
- rapporto eventi/memorie persistite;
- percentuale di task estratti correttamente;
- percentuale di reminder contestuali attivati correttamente;
- qualità della diarizzazione;
- accuratezza speaker association;
- costo LLM giornaliero;
- storage giornaliero;
- percentuale di elaborazione locale;
- numero di interruzioni non utili;
- capacità di ritrovare informazioni realmente richieste.


30. Visione evolutiva
Project Mnemos deve poter evolvere da prototipo personale a piattaforma generalizzabile. Il valore non risiede nel singolo wearable ma nel core di Perception + Entity Resolution + Memory + Decision + Reasoning + Action. Ogni nuovo sensore diventa una nuova fonte del medesimo World Model, mentre ogni nuova integrazione diventa un nuovo canale di azione.


La visione finale è un Persistent Cognitive Assistant che condivide progressivamente il contesto operativo dell'utente, senza richiedere che tutto venga esplicitamente scritto o ricordato manualmente
31. Remote Mobile Sensor Gateway
Project Mnemos deve poter utilizzare uno smartphone come sensore remoto audio/video, mantenendo il computer come local brain. Questa modalità è parte del percorso MVP e deve essere utilizzabile prima dell'integrazione con smart glasses.


Funzioni richieste:
- streaming realtime della camera dello smartphone verso il computer;
- streaming realtime del microfono dello smartphone verso il computer;
- possibilità di usare camera posteriore o frontale;
- gestione orientamento, risoluzione, FPS e qualità;
- timestamp e sincronizzazione audio/video;
- riconnessione automatica e gestione perdita rete;
- pairing/autorizzazione del dispositivo;
- supporto iniziale su rete locale e possibilità futura di funzionamento attraverso Internet;
- telemetria di latenza, bitrate, packet loss e stato connessione;
- comando remoto di start/stop/pause dei sensori;
- possibilità di visualizzare sul telefono lo stato del core e le risposte essenziali.


Il telefono non deve contenere il core cognitivo completo: agisce principalmente come sensor gateway e interfaccia. Il flusso deve poter essere inviato al local brain che esegue perception, memory e decision logic. Parte dell'inferenza leggera potrà essere spostata sul telefono in futuro per ridurre banda o latenza.


Il protocollo di trasporto sarà deciso nell'architettura tecnica. WebRTC è un candidato naturale per audio/video realtime, ma la scelta deve essere confrontata con alternative LAN-first e con i requisiti di autenticazione, semplicità di sviluppo, latenza e funzionamento remoto.


Questa modalità deve consentire il test realistico di Project Mnemos muovendosi liberamente con il telefono in mano, prima che il wearable diventi disponibile.


32. Identità dell'assistente: Tobi
L'interfaccia conversazionale e vocale del sistema si chiama Tobi. Tobi è la personalità/interfaccia del core Mnemos e può rispondere tramite dashboard, browser del telefono e in futuro wearable. Il sistema non richiede obbligatoriamente una wake word: l'ascolto locale può restare attivo, mentre intent detection, speaker recognition e contesto stabiliscono se una frase è rivolta al sistema. Pronunciare esplicitamente "Tobi" aumenta la confidenza che si tratti di un comando o di una domanda diretta.


33. Browser Phone Sensor
Nell'MVP lo smartphone non richiede un'app nativa. Il computer espone una sessione di pairing tramite QR/link locale. Aprendo il link da un browser mobile autorizzato, il telefono può fornire camera e microfono al local brain attraverso tecnologie web compatibili con realtime media.


Funzioni minime:
- pairing QR/link sulla LAN;
- richiesta permessi camera e microfono;
- camera frontale/posteriore;
- stream audio/video realtime;
- preview locale;
- start, pause e stop;
- ricezione di stato, reminder e risposte da Tobi;
- riproduzione TTS proveniente dal core;
- telemetria di qualità e connessione.


L'app nativa smartphone è esplicitamente rinviata finché non emergeranno requisiti di background execution, on-device inference o integrazione wearable che il browser non può soddisfare.


34. Rolling Buffer operativo
Per la fase sperimentale il sistema mantiene fino a cinque minuti di rolling buffer locale audio e, quando sostenibile, video a qualità controllata. Il buffer è circolare e viene sovrascritto automaticamente. Serve a consentire richieste immediate come "fammi risentire quello che ha detto poco fa" e a estrarre clip di evidenza senza archiviare l'intera giornata.


Il contenuto del rolling buffer non costituisce memoria permanente. Una clip viene resa persistente solo per registrazione esplicita, modalità meeting/evidence o selezione event-driven prevista dalle policy.


35. Prima demo end-to-end
La prima demo di riferimento deve mostrare:
- browser telefono associato al Mac tramite QR;
- camera e microfono inviati al core;
- riconoscimento classi generiche con overlay realtime;
- face detection;
- OCR;
- trascrizione italiana/inglese;
- enrollment di un oggetto specifico da voce e dashboard;
- successivo riconoscimento dello stesso oggetto con nome, evidenze e last seen;
- enrollment/identificazione di una persona autorizzata;
- creazione e attivazione di un reminder contestuale;
- query di memoria attraverso Tobi.


Questa demo rappresenta una vertical slice e deve guidare l'ordine di implementazione prima dell'espansione a casi più complessi.
.