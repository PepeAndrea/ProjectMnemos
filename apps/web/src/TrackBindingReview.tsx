import {useEffect,useState} from 'react';

export type ObjectChoice = {id:string;kind:string;name:string};
export type VisibleTrack = {track_id:string;label:string;confidence:number;entity_id?:string;session_name?:{name:string;source:string;verified_identity:false};box:{x:number;y:number;width:number;height:number}};

export function TrackBindingReview({tracks,objects,disabled,onBind}:{tracks:VisibleTrack[];objects:ObjectChoice[];disabled:boolean;onBind:(trackId:string,entityId:string)=>Promise<void>}) {
  const [trackId,setTrackId]=useState('');
  const [entityId,setEntityId]=useState('');
  const [confirmed,setConfirmed]=useState(false);
  const choices=tracks.filter(track=>!track.entity_id&&!['person','face'].includes(track.label));
  const valid=choices.some(track=>track.track_id===trackId)&&objects.some(entity=>entity.id===entityId);
  useEffect(()=>{
    if(trackId&&!tracks.some(track=>track.track_id===trackId&&!track.entity_id&&!['person','face'].includes(track.label))){setTrackId('');setConfirmed(false);}
    if(entityId&&!objects.some(entity=>entity.id===entityId)){setEntityId('');setConfirmed(false);}
  },[tracks,objects,trackId,entityId]);
  return <form className="track-review" onSubmit={event=>{event.preventDefault();if(disabled||!valid||!confirmed)return;void onBind(trackId,entityId).then(()=>{setConfirmed(false);setTrackId('');});}}>
    <h3>Associa un oggetto del feed</h3>
    <p>Scegli la track e il nome già registrato. La tua conferma vale nella sessione corrente; una perdita della track richiede nuove evidenze. Nessuna immagine viene salvata.</p>
    <label htmlFor="observed-track">Oggetto osservato</label><select id="observed-track" value={trackId} disabled={disabled} onChange={event=>{setTrackId(event.target.value);setConfirmed(false);}}><option value="">Scegli una track</option>{choices.map((track,index)=><option key={track.track_id} value={track.track_id}>{track.label} · track {index+1} · {Math.round(track.confidence*100)}% detector</option>)}</select>
    <label htmlFor="observed-entity">Oggetto del catalogo</label><select id="observed-entity" value={entityId} disabled={disabled} onChange={event=>{setEntityId(event.target.value);setConfirmed(false);}}><option value="">Scegli un nome</option>{objects.map(entity=><option key={entity.id} value={entity.id}>{entity.name}</option>)}</select>
    <label className="check"><input type="checkbox" checked={confirmed} disabled={disabled||!valid} onChange={event=>setConfirmed(event.target.checked)}/>Confermo che la track selezionata è questo oggetto</label>
    <button disabled={disabled||!valid||!confirmed}>Associa nella sessione</button>
    {!choices.length&&<p className="empty">Nessuna track di oggetto disponibile. Le persone hanno un percorso dedicato.</p>}
  </form>;
}
