import {useEffect,useRef,useState} from 'react';
import type {ObjectChoice,VisibleTrack} from './TrackBindingReview';

export function ReferenceSave({captureId,tracks,objects,token,disabled,onSaved}:{captureId:string;tracks:VisibleTrack[];objects:ObjectChoice[];token:string;disabled:boolean;onSaved:()=>Promise<void>}) {
  const [trackId,setTrackId]=useState('');
  const [expiry,setExpiry]=useState('');
  const [confirmed,setConfirmed]=useState(false);
  const [busy,setBusy]=useState(false);
  const [message,setMessage]=useState('');
  const abort=useRef<AbortController|undefined>(undefined);
  const bound=tracks.filter(track=>track.entity_id&&objects.some(entity=>entity.id===track.entity_id));
  const selected=bound.find(track=>track.track_id===trackId);
  useEffect(()=>{const controller=new AbortController();abort.current=controller;setTrackId('');setExpiry('');setConfirmed(false);setMessage('');setBusy(false);return()=>controller.abort();},[token,captureId]);
  useEffect(()=>{if(trackId&&!bound.some(track=>track.track_id===trackId)){setTrackId('');setConfirmed(false);}},[tracks,objects,trackId]);
  async function save() {
    const controller=abort.current;
    if(!selected||!confirmed||disabled||busy||!expiry||!controller||controller.signal.aborted)return;
    const deadline=new Date(expiry);
    if(!Number.isFinite(deadline.getTime())||deadline.getTime()<=Date.now()){setMessage('Scegli una scadenza futura.');return;}
    setBusy(true);setMessage('');
    try {
      const response=await fetch('/api/capture/'+captureId+'/tracks/'+trackId+'/reference',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},cache:'no-store',signal:controller.signal,body:JSON.stringify({entity_id:selected.entity_id,expires_at:deadline.toISOString(),confirm_object_only_reference:true})});
      if(!response.ok)throw new Error(response.status===403?'Il crop deve essere libero da persone e volti.':response.status===404||response.status===409?'La track non è più disponibile.':response.status===422?'Crop o scadenza non validi, oppure limite reference raggiunto.':'Salvataggio non confermato. Aggiorna le reference prima di riprovare.');
      if(controller.signal.aborted)return;
      setConfirmed(false);setMessage('Reference salvata. Puoi visualizzarla nel pannello Reference degli oggetti.');
      await onSaved();
    } catch(error){if(!controller.signal.aborted)setMessage(error instanceof Error?error.message:'Salvataggio non riuscito.');}
    finally{if(!controller.signal.aborted)setBusy(false);}
  }
  return <form className="reference-save" onSubmit={event=>{event.preventDefault();void save();}}>
    <h3>Salva una reference dell’oggetto</h3>
    <p>Salva il crop corrente di una track che hai associato. Controlla nel feed che l’oggetto sia interamente visibile e libero da persone e volti. La reference resta sul Mac fino alla scadenza o alla revoca.</p>
    <label htmlFor="reference-track">Track associata</label><select id="reference-track" value={trackId} disabled={disabled||busy} onChange={event=>{setTrackId(event.target.value);setConfirmed(false);}}><option value="">Scegli un oggetto associato</option>{bound.map(track=><option key={track.track_id} value={track.track_id}>{objects.find(entity=>entity.id===track.entity_id)?.name} · track {tracks.indexOf(track)+1}</option>)}</select>
    <label htmlFor="reference-expiry">Scadenza della reference · ora locale</label><input id="reference-expiry" type="datetime-local" value={expiry} onInput={event=>setExpiry(event.currentTarget.value)} onChange={event=>setExpiry(event.target.value)} disabled={disabled||busy} required/>
    <label className="check"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)} disabled={disabled||busy||!selected}/>Confermo il salvataggio del solo oggetto, senza persone nel crop</label>
    <button disabled={disabled||busy||!selected||!confirmed||!expiry}>Salva reference corrente</button>
    {message&&<p role="status">{message}</p>}
  </form>;
}
