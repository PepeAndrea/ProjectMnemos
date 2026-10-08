import {useEffect, useRef, useState} from 'react';
import {SessionPersonNames} from './SessionPersonNames';
import {ReferenceSave} from './ReferenceSave';
import {FaceReferenceSave} from './FaceReferenceSave';
import type {Person} from './PeoplePanel';
import {VoiceEnrollmentReview, type EnrollmentProposal,type PersonVoiceConsent} from './VoiceEnrollmentReview';

import {TrackBindingReview, type ObjectChoice, type VisibleTrack} from './TrackBindingReview';

type Detection = {label:string; confidence:number; box:{x:number;y:number;width:number;height:number}};
type Transcript = {id:string;text:string;partial:boolean;language:string;confidence:number;start_seconds:number;end_seconds:number};
type CaptureStatus = {id?:string;tracks?:VisibleTrack[];enrollment_proposals?:EnrollmentProposal[];state:string; camera?:boolean; microphone?:boolean;transcribing?:boolean;transcripts?:Transcript[];audio_queue_depth?:number;audio_drops?:number;speech_latency_ms?:number;speech_discontinuities?:number; error?:string; error_code?:string;worker_active?:boolean;source_cleanup_failed?:boolean; width?:number; height?:number; processed_frames?:number; drops?:number; queue_depth?:number; latency_ms?:number; recording:boolean; detections?:Detection[]};

export function CapturePanel({token,connected,onEnrolled,objects,people}:{token:string;connected:boolean;onEnrolled:()=>Promise<void>;objects:ObjectChoice[];people:Person[]}) {
  const [capture,setCapture] = useState<CaptureStatus>({state:'idle',recording:false});
  const [preview,setPreview] = useState<string>();
  const [cameraConsent,setCameraConsent] = useState(false);
  const [cameraIndex,setCameraIndex] = useState('');
  const [micConsent,setMicConsent] = useState(false);
  const [error,setError] = useState('');
  const [pollError,setPollError] = useState('');
  const [busy,setBusy] = useState(false);
  const requestAbort=useRef<AbortController|undefined>(undefined);
  useEffect(()=>{
    const abort = new AbortController();requestAbort.current=abort;setBusy(false);
    let objectUrl:string|undefined;
    let pending = false;
    setCapture({state:'idle',recording:false}); setPreview(undefined); setError('');setPollError('');
    if(!connected) {setCameraConsent(false);setMicConsent(false);return ()=>abort.abort();}
    async function poll() {
      if(pending||abort.signal.aborted) return;
      pending = true;
      try {
        const response = await fetch('/api/capture/status',{headers:{Authorization:'Bearer '+token},cache:'no-store',signal:abort.signal});
        if(!response.ok) throw new Error('Stato del sensore non disponibile.');
        const state:CaptureStatus = await response.json();
        if(abort.signal.aborted) return;
        setCapture(state);setPollError('');
        if(state.state==='running') {
          const frame = await fetch('/api/capture/frame',{headers:{Authorization:'Bearer '+token},cache:'no-store',signal:abort.signal});
          if(frame.ok) {
            const blob = await frame.blob();
            if(abort.signal.aborted) return;
            const next = URL.createObjectURL(blob);
            if(objectUrl) URL.revokeObjectURL(objectUrl);
            objectUrl = next; setPreview(next);
          }
        } else {
          if(objectUrl) URL.revokeObjectURL(objectUrl);
          objectUrl=undefined;setPreview(undefined);
        }
      } catch(e) {
        if(!abort.signal.aborted) {if(objectUrl) URL.revokeObjectURL(objectUrl);objectUrl=undefined;setPollError(e instanceof Error?e.message:'Collegamento interrotto.');setPreview(undefined);setCapture({state:'unavailable',recording:false});}
      } finally {pending=false;}
    }
    void poll(); const timer=window.setInterval(()=>void poll(),500);
    return ()=>{abort.abort();window.clearInterval(timer);if(objectUrl) URL.revokeObjectURL(objectUrl);};
  },[token,connected]);
  async function control(action:'start'|'stop',mode:'replay'|'native'|'speech-replay'='replay') {
    const abort=requestAbort.current;if(!connected||!abort||abort.signal.aborted)return;
    setBusy(true);setError('');
    try {
      const response=await fetch('/api/capture/'+action,{method:'POST',signal:abort.signal,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:action==='start'?JSON.stringify({mode,camera:mode==='speech-replay'?false:mode==='replay'||cameraConsent,microphone:mode!=='native'||micConsent,camera_consent:cameraConsent,camera_index:mode==='native'&&cameraIndex!==''?Number(cameraIndex):null,microphone_consent:micConsent,transcribe:mode==='speech-replay'||(mode==='native'&&micConsent),language:'it'}):undefined});
      if(!response.ok) throw new Error(response.status===409?'Un sensore è già attivo. Fermalo prima di riavviare.':'Impossibile avviare o fermare il sensore.');
      const next:CaptureStatus=await response.json();if(abort.signal.aborted)return;setCapture(next);
      if(action==='stop') setPreview(undefined);
    } catch(e) {if(!abort.signal.aborted)setError(e instanceof Error?e.message:'Operazione fallita.');}
    finally {if(!abort.signal.aborted)setBusy(false);}
  }
  async function review(id:string,action:'approve'|'reject',name?:string,person?:PersonVoiceConsent) {
    const sessionId=capture.id;
    if(!sessionId||capture.state!=='running') return;
    const abort=requestAbort.current;if(!connected||!abort||abort.signal.aborted)return;
    setBusy(true);setError('');
    try {
      const route=action==='approve'&&person?'approve-person':action;
      const response=await fetch('/api/capture/'+sessionId+'/enrollment/'+id+'/'+route,{method:'POST',signal:abort.signal,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:action==='approve'?JSON.stringify(person?{name,...person,confirm_person_enrollment:true}:{name,confirm_catalog_enrollment:true}):undefined,cache:'no-store'});
      if(!response.ok) throw new Error(response.status===404||response.status===409?'La proposta è scaduta o è già stata elaborata.':'Registrazione non riuscita. Aggiorna il catalogo prima di riprovare.');
      if(abort.signal.aborted)return;
      setCapture(current=>current.id===sessionId?{...current,enrollment_proposals:current.enrollment_proposals?.filter(item=>item.id!==id)}:current);
      if(action==='approve') await onEnrolled();
    } catch(e) {if(!abort.signal.aborted)setError(e instanceof Error?e.message:'Revisione non riuscita.');}
    finally {if(!abort.signal.aborted)setBusy(false);}
  }
  async function bind(trackId:string,entityId:string) {
    const abort=requestAbort.current;const sessionId=capture.id;
    if(!connected||!sessionId||!abort||abort.signal.aborted)return;
    setBusy(true);setError('');
    try {
      const response=await fetch('/api/capture/'+sessionId+'/tracks/'+trackId+'/bind',{method:'POST',signal:abort.signal,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({entity_id:entityId,confirm_observed_object:true}),cache:'no-store'});
      if(!response.ok)throw new Error(response.status===404||response.status===409?'La track è cambiata. Scegli di nuovo l’oggetto.':'Associazione non riuscita.');
      const result:{bound:boolean}=await response.json();if(abort.signal.aborted)return;
      if(!result.bound)setError('La track è terminata durante la conferma. Il catalogo resta disponibile.');
    } catch(e){if(!abort.signal.aborted)setError(e instanceof Error?e.message:'Associazione non riuscita.');}
    finally{if(!abort.signal.aborted)setBusy(false);}
  }
  async function namePerson(trackId:string,name:string) {
    const abort=requestAbort.current;const sessionId=capture.id;
    if(!connected||!sessionId||!abort||abort.signal.aborted)return;
    setBusy(true);setError('');
    try {
      const response=await fetch('/api/capture/'+sessionId+'/faces/'+trackId+'/name',{method:'PUT',signal:abort.signal,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({name}),cache:'no-store'});
      if(!response.ok)throw new Error('Il viso non è più disponibile. Selezionalo nuovamente.');
    } catch(e){if(!abort.signal.aborted)setError(e instanceof Error?e.message:'Nome non assegnato.');}
    finally{if(!abort.signal.aborted)setBusy(false);}
  }
  const running = capture.state==='running'||capture.state==='starting';
  const workerActive = running||capture.worker_active===true;
  const stateUnknown=capture.state==='unavailable';
  const sourceMessages:Record<string,string>={
    'speech-asr-failed':'Il modello di trascrizione locale ha interrotto l’elaborazione. Ferma i sensori e riprova; se ricapita, verifica il modello e il runtime Whisper.',
    'speech-output-invalid':'Il modello ha restituito un risultato fuori formato. I dati temporanei sono stati cancellati. Ferma i sensori e riprova.',
    'speech-vad-failed':'Il rilevatore locale del parlato non è disponibile. Verifica il modello Silero e il runtime.',
    'speech-processing-failed':'La trascrizione locale si è interrotta. Il microfono può aver funzionato correttamente: ferma i sensori e riprova.',
    'camera-open-failed':'Camera non disponibile. Controlla il collegamento, i permessi Camera di macOS per il programma che avvia il core e se un’altra app la sta usando. Poi riprova.',
    'camera-stream-ended':'La camera ha smesso di inviare frame. Controlla il collegamento e riavvia i sensori quando la pulizia è terminata.',
    'video-file-unavailable':'Il video di replay non si apre. Verifica che la fixture locale sia disponibile.',
    'video-file-unreadable':'Il video di replay non contiene frame leggibili o la lettura si è interrotta.',
    'video-frame-invalid':'La sorgente ha restituito un frame fuori formato o troppo grande. Prova una sorgente compatibile.',
    'microphone-open-failed':'Microfono non disponibile. Controlla il dispositivo e i permessi Microfono di macOS per il programma che avvia il core. Poi riprova.',
    'microphone-read-failed':'La lettura del microfono si è interrotta. Controlla il dispositivo e riavvia dopo la pulizia.',
    'video-source-failed':'Acquisizione video non disponibile. Verifica la sorgente e le dipendenze locali.',
    'audio-source-failed':'Acquisizione audio non disponibile. Verifica la sorgente e le dipendenze locali.',
    'video-close-failed':'Il rilascio della sorgente video non è stato confermato. Controlla il dispositivo prima di riprovare.',
    'microphone-close-failed':'Il rilascio del microfono non è stato confermato. Controlla il dispositivo prima di riprovare.',
    'sensor-cleanup-failed':'La pulizia dei sensori non è stata completata. Controlla il dispositivo e il core prima di riprovare.'
  };
  const sourceError=capture.error_code?sourceMessages[capture.error_code]||capture.error:capture.error;
  return <section className="capture-panel">
    <div className="section-title"><h2>Percezione locale</h2><span className="status" role="status">{capture.state}</span></div>
    <p>Feed e riconoscimenti restano sul Mac. I buffer vengono svuotati allo stop.</p>
    <div className="live-view">{preview?<><img src={preview} alt="Feed del sensore attivo"/>{capture.tracks?.map((d,index)=><div key={index} className="detection" style={{left:Math.max(0,d.box.x/(capture.width||1)*100)+'%',top:Math.max(0,d.box.y/(capture.height||1)*100)+'%',width:Math.min(100,d.box.width/(capture.width||1)*100)+'%',height:Math.min(100,d.box.height/(capture.height||1)*100)+'%'}}><span>{d.session_name?.name||objects.find(entity=>entity.id===d.entity_id)?.name||d.label+' · track '+(index+1)}{d.session_name?' · nome provvisorio':d.entity_id?' · confermato da te':''} · {Math.round(d.confidence*100)}% detector</span></div>)}</>:<span>{capture.state==='starting'?'Preparo i modelli locali…':running?(capture.camera?'Attendo il primo frame…':'Acquisizione solo audio'):'Nessun sensore attivo'}</span>}</div>
    <div className="row"><button disabled={!connected||busy||workerActive||stateUnknown} onClick={()=>void control('start')}>Avvia replay di verifica</button><button disabled={!connected||busy||workerActive||stateUnknown} onClick={()=>void control('start','speech-replay')}>Avvia replay vocale italiano</button><button className="secondary" disabled={!connected||busy||(!workerActive&&!stateUnknown)} onClick={()=>void control('stop')}>Stop sensori</button></div>
    <fieldset><legend>Consenso per i sensori del Mac</legend><label className="check"><input type="checkbox" checked={cameraConsent} onChange={e=>setCameraConsent(e.target.checked)} disabled={workerActive||stateUnknown}/>Consento l’uso della camera locale</label><label>Camera da usare<select value={cameraIndex} onChange={e=>setCameraIndex(e.target.value)} disabled={!cameraConsent||workerActive||stateUnknown}><option value="">Automatica (prova gli indici 0–4)</option>{[0,1,2,3,4].map(index=><option key={index} value={index}>Camera {index}</option>)}</select></label><p className="telemetry">OpenCV mostra gli indici, non i nomi dei dispositivi. Avvia la camera per verificare il feed e scegli l’indice corrispondente alla webcam.</p><label className="check"><input type="checkbox" checked={micConsent} onChange={e=>setMicConsent(e.target.checked)} disabled={workerActive||stateUnknown}/>Consento microfono e trascrizione locale</label><button disabled={!connected||busy||workerActive||stateUnknown||(!cameraConsent&&!micConsent)} onClick={()=>void control('start','native')}>Avvia i sensori selezionati</button></fieldset>
    <p className="telemetry">Frame elaborati: {capture.processed_frames||0} · Scartati: {capture.drops||0} · Coda: {capture.queue_depth||0} · Inferenza: {Math.round(capture.latency_ms||0)} ms · Registrazione: spenta</p>
    <div className="transcript" aria-live="polite"><h3>Trascrizione locale</h3><p>Lingua predefinita: italiano. Testo temporaneo, cancellato allo stop. Il parlante resta anonimo.</p>{capture.transcripts?.map(item=><p key={item.id}><span className="status">{item.language.toUpperCase()} · {item.partial?'parziale':'finale'} · {Math.round(item.confidence*100)}%</span> {item.text}</p>)}{!capture.transcripts?.length&&<p className="empty">{capture.state==='completed'?'Sorgente terminata. Il testo temporaneo è stato cancellato.':capture.transcribing?'Attendo il parlato…':'La trascrizione si attiva con il microfono.'}</p>}<p className="telemetry">Coda audio: {capture.audio_queue_depth||0} · Scartati: {capture.audio_drops||0} · Pipeline vocale: {Math.round(capture.speech_latency_ms||0)} ms · Discontinuità: {capture.speech_discontinuities||0}</p></div>
    {capture.tracks?.filter(track=>track.entity_id).map(track=>{const entity=objects.find(item=>item.id===track.entity_id);return entity?<p key={track.track_id}>{entity.name} · Confermato da te nella sessione</p>:null;})}
    {running&&capture.camera&&<SessionPersonNames key={'names-'+capture.id} tracks={capture.tracks||[]} disabled={!connected||busy||capture.state!=='running'} onName={namePerson}/>}
    {running&&capture.camera&&<TrackBindingReview key={capture.id} tracks={capture.tracks||[]} objects={objects} disabled={!connected||busy||capture.state!=='running'} onBind={bind}/>}
    {running&&capture.camera&&capture.id&&<ReferenceSave key={'reference-'+capture.id} captureId={capture.id} tracks={capture.tracks||[]} objects={objects} token={token} disabled={!connected||busy||capture.state!=='running'} onSaved={onEnrolled}/>}
    {running&&capture.camera&&capture.id&&<FaceReferenceSave key={'face-reference-'+capture.id} captureId={capture.id} tracks={capture.tracks||[]} people={people} token={token} disabled={!connected||busy||capture.state!=='running'}/>}
    {capture.enrollment_proposals?.map(proposal=><VoiceEnrollmentReview key={proposal.id} proposal={proposal} disabled={!connected||busy||capture.state!=='running'} onReview={review}/>)}
    {(error||pollError||sourceError)&&<p className="error" role="alert">{error||pollError||sourceError}</p>}
    {capture.source_cleanup_failed&&<p className="error" role="alert">Il driver ha segnalato un problema nel rilascio del dispositivo. I dati temporanei sono stati cancellati; verifica il dispositivo prima di riprovare.</p>}
    {capture.state==='failed'&&workerActive&&<p role="status">Pulizia dei sensori in corso. Puoi premere Stop; un nuovo avvio sarà disponibile quando i worker saranno terminati.</p>}
  </section>;
}
