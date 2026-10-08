import {useEffect,useState} from 'react';
import type {VisibleTrack} from './TrackBindingReview';

export function SessionPersonNames({tracks,disabled,onName}:{tracks:VisibleTrack[];disabled:boolean;onName:(trackId:string,name:string)=>Promise<void>}) {
  const faces=tracks.filter(track=>track.label==='face');
  const [trackId,setTrackId]=useState('');
  const [name,setName]=useState('');
  useEffect(()=>{if(trackId&&!faces.some(track=>track.track_id===trackId)){setTrackId('');setName('');}},[tracks,trackId]);
  return <form className="track-review" onSubmit={event=>{event.preventDefault();if(!disabled&&faces.some(track=>track.track_id===trackId)&&name.trim()) void onName(trackId,name.trim());}}>
    <h3>Nomi delle persone nella sessione</h3><p>«Mi chiamo Andrea» o «Questa persona si chiama Andrea» assegna automaticamente un nome provvisorio se un solo viso rimane visibile durante la frase. Puoi correggerlo qui. Il nome scompare quando perdiamo la track o fermi i sensori; non conferma chi sta parlando e non registra un’identità biometrica.</p>
    <label htmlFor="session-person-track">Viso osservato</label><select id="session-person-track" value={trackId} disabled={disabled} onChange={event=>{setTrackId(event.target.value);setName(faces.find(track=>track.track_id===event.target.value)?.session_name?.name||'');}}><option value="">Scegli un viso</option>{faces.map((track,index)=><option key={track.track_id} value={track.track_id}>Viso {index+1}{track.session_name?' · '+track.session_name.name:''}</option>)}</select>
    <label htmlFor="session-person-name">Nome da assegnare</label><input id="session-person-name" value={name} onChange={event=>setName(event.target.value)} maxLength={80} disabled={disabled||!trackId}/><button disabled={disabled||!trackId||!name.trim()}>Assegna nome</button>
    {!faces.length&&<p className="empty">Nessun viso disponibile.</p>}
  </form>;
}
