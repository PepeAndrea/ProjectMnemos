import {useEffect,useRef,useState} from 'react';
import type {Person} from './PeoplePanel';
import type {VisibleTrack} from './TrackBindingReview';

export function FaceReferenceSave({captureId,tracks,people,token,disabled}:{captureId:string;tracks:VisibleTrack[];people:Person[];token:string;disabled:boolean}) {
  const [trackId,setTrackId]=useState('');const [personId,setPersonId]=useState('');
  const [expiry,setExpiry]=useState('');const [confirmed,setConfirmed]=useState(false);
  const [busy,setBusy]=useState(false);const [error,setError]=useState('');const [message,setMessage]=useState('');
  const abortRef=useRef(new AbortController());
  const faces=tracks.filter(track=>track.label==='face');
  const permitted=people.filter(person=>person.face&&Date.parse(person.expires_at)>Date.now());
  const person=permitted.find(value=>value.id===personId);
  const deadline=expiry?new Date(expiry):undefined;
  const valid=person&&faces.some(face=>face.track_id===trackId)&&confirmed&&deadline&&Number.isFinite(deadline.getTime())&&deadline.getTime()>Date.now()&&deadline.getTime()<=Date.parse(person.expires_at);
  useEffect(()=>{const abort=new AbortController();abortRef.current=abort;return()=>abort.abort();},[token,captureId]);
  useEffect(()=>{if(trackId&&!faces.some(face=>face.track_id===trackId)){setTrackId('');setConfirmed(false);}if(personId&&!person){setPersonId('');setConfirmed(false);}},[tracks,people,trackId,personId]);
  useEffect(()=>{setConfirmed(false);setMessage('');},[trackId,personId,person?.name,person?.expires_at]);
  async function save(){
    const signal=abortRef.current.signal;if(disabled||busy||!valid||!person||signal.aborted)return;
    setBusy(true);setError('');setMessage('');
    try {
      const response=await fetch('/api/capture/'+captureId+'/faces/'+trackId+'/reference',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},cache:'no-store',signal,body:JSON.stringify({entity_id:person.id,confirmed_name:person.name,expires_at:deadline!.toISOString(),confirm_face_reference:true})});
      if(!response.ok)throw new Error(response.status===403?'Consenso al viso o conferma non validi.':response.status===422?'Immagine, scadenza o vista duplicata non valide. Migliora la vista e riprova.':'Volto o persona non più disponibili.');
      if(signal.aborted)return;setConfirmed(false);setMessage('Reference del viso salvata. Puoi rivederla nel pannello dei visi autorizzati.');
    }catch(err){if(!signal.aborted)setError(err instanceof Error?err.message:'Salvataggio non riuscito.');}
    finally{if(!signal.aborted)setBusy(false);}
  }
  return <form className="reference-save" onSubmit={event=>{event.preventDefault();void save();}}><h3>Salva il viso di una persona autorizzata</h3>
    <p>Seleziona nel feed un volto interamente visibile e la persona con consenso al viso valido. Salverai il crop corrente: verifica che sia proprio quella persona e che non includa altri volti. Questa scelta non autorizza comandi o registrazioni di conversazioni.</p>
    <label htmlFor="face-reference-track">Volto osservato</label><select id="face-reference-track" value={trackId} disabled={disabled||busy} onChange={event=>setTrackId(event.target.value)}><option value="">Scegli una track del viso</option>{faces.map(face=><option key={face.track_id} value={face.track_id}>Viso · track {tracks.findIndex(item=>item.track_id===face.track_id)+1} · {Math.round(face.confidence*100)}% detector</option>)}</select>
    <label htmlFor="face-reference-person-save">Persona con consenso al viso</label><select id="face-reference-person-save" value={personId} disabled={disabled||busy} onChange={event=>setPersonId(event.target.value)}><option value="">Scegli una persona autorizzata</option>{permitted.map(value=><option key={value.id} value={value.id}>{value.name}</option>)}</select>
    {person&&<p>Consenso fino al {new Date(person.expires_at).toLocaleString()}.</p>}
    <label htmlFor="face-reference-expiry">Scadenza della reference del viso · ora locale</label><input id="face-reference-expiry" type="datetime-local" value={expiry} onInput={event=>setExpiry(event.currentTarget.value)} onChange={event=>setExpiry(event.target.value)} disabled={disabled||busy} required/>
    <label className="check"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)} disabled={disabled||busy||!person||!trackId}/>Confermo che il volto selezionato appartiene alla persona scelta e consento il salvataggio del suo solo viso</label>
    <button disabled={disabled||busy||!valid}>Salva reference del viso corrente</button>
    {!permitted.length&&<p>Nessuna persona con consenso al viso valido.</p>}{!faces.length&&<p>Nessuna track del viso disponibile.</p>}
    {error&&<p className="error" role="alert">{error}</p>}{message&&<p role="status">{message}</p>}
  </form>;
}
