import {useEffect,useRef,useState} from 'react';
import type {ObjectChoice} from './TrackBindingReview';
type ReferenceQuality = {version:number;width:number;height:number;warnings:string[];face?:{version:number;calibrated:boolean;landmarks_available:boolean;eye_line_roll_degrees?:number}};
type Reference = {id:string;expires_at:string;observed_at:string;quality?:ReferenceQuality|null};
const qualityWarnings:Record<string,string>={'low-contrast':'contrasto basso','low-edge-detail':'pochi dettagli visibili','clipped-exposure':'esposizione saturata','face-low-detail':'viso con pochi dettagli: verifica fuoco e luce','face-geometry-unavailable':'geometria del viso non valutata','face-landmarks-outside-crop':'punti del viso fuori dal crop','face-degenerate-geometry':'geometria del viso da rifare','face-tilted-eye-line':'linea degli occhi inclinata','face-small-eye-span':'occhi troppo vicini nell’immagine','face-asymmetric-proxy':'geometria asimmetrica: aggiungi anche una vista frontale'};
function describeQuality(quality?:ReferenceQuality|null){
  if(!quality||quality.version!==1)return 'Qualità non valutata per questa reference.';
  const warnings=quality.warnings.map(value=>qualityWarnings[value]||'controllo da rivedere');
  const geometry=quality.face?.version===1&&quality.face.eye_line_roll_degrees!==undefined?' · Linea occhi: '+Math.round(quality.face.eye_line_roll_degrees)+'° · misura non calibrata':'';
  return quality.width+' × '+quality.height+' px · '+(warnings.length?'Da rivedere: '+warnings.join(', '):'Nessun avviso nei controlli di base.')+geometry;
}

export function ReferencePanel({objects,token,connected,kind='object'}:{objects:ObjectChoice[];token:string;connected:boolean;kind?:'object'|'face'}) {
  const face=kind==='face';const route=face?'/face-references/':'/references/';
  const [entityId,setEntityId]=useState('');
  const [references,setReferences]=useState<Reference[]>([]);
  const [selected,setSelected]=useState('');
  const [image,setImage]=useState<string>();
  const [error,setError]=useState('');
  const [confirmedName,setConfirmedName]=useState('');
  const [confirmed,setConfirmed]=useState(false);
  const [busy,setBusy]=useState(false);
  const controller=useRef<AbortController|undefined>(undefined);
  const blobUrl=useRef<string|undefined>(undefined);
  const selectedRef=useRef('');
  const imageGeneration=useRef(0);const listGeneration=useRef(0);
  const entity=objects.find(item=>item.id===entityId);
  function clearImage(){imageGeneration.current+=1;if(blobUrl.current)URL.revokeObjectURL(blobUrl.current);blobUrl.current=undefined;selectedRef.current='';setSelected('');setImage(undefined);setConfirmed(false);setConfirmedName('');}
  useEffect(()=>{setEntityId('');clearImage();setReferences([]);setError('');},[token,connected]);
  useEffect(()=>{if(entityId&&!objects.some(item=>item.id===entityId))setEntityId('');},[objects,entityId]);
  useEffect(()=>{
    const abort=new AbortController();controller.current=abort;listGeneration.current+=1;clearImage();setReferences([]);setError('');setBusy(false);
    let timer:number|undefined;
    async function poll(){
      if(abort.signal.aborted)return;
      const generation=listGeneration.current;
      try {
        const response=await fetch('/api'+(face?'/people/'+entityId+'/face-references':'/objects/'+entityId+'/references'),{headers:{Authorization:'Bearer '+token},cache:'no-store',signal:abort.signal});
        if(!response.ok)throw new Error('Reference non disponibili.');
        const rows:Reference[]=await response.json();if(abort.signal.aborted||generation!==listGeneration.current)return;
        const active=rows.filter(row=>Date.parse(row.expires_at)>Date.now());setReferences(active);
        if(selectedRef.current&&!active.some(row=>row.id===selectedRef.current))clearImage();
        setError('');
      }catch(err){if(!abort.signal.aborted){clearImage();setReferences([]);setError(err instanceof Error?err.message:'Core non disponibile.');}}
      finally{if(!abort.signal.aborted)timer=window.setTimeout(()=>void poll(),2000);}
    }
    if(connected&&entityId)void poll();
    return()=>{abort.abort();if(timer)window.clearTimeout(timer);if(blobUrl.current)URL.revokeObjectURL(blobUrl.current);blobUrl.current=undefined;selectedRef.current='';};
  },[connected,token,entityId,kind]);
  useEffect(()=>{
    if(!selected)return;
    const timer=window.setInterval(()=>{const row=references.find(item=>item.id===selected);if(!row||Date.parse(row.expires_at)<=Date.now())clearImage();},500);
    return()=>window.clearInterval(timer);
  },[selected,references]);
  async function show(id:string){
    const abort=controller.current;if(!connected||busy||!abort||abort.signal.aborted)return;
    clearImage();const generation=imageGeneration.current;setBusy(true);setError('');
    try {
      const response=await fetch('/api'+route+id+'/image',{headers:{Authorization:'Bearer '+token},cache:'no-store',signal:abort.signal});
      if(!response.ok)throw new Error('Reference scaduta, revocata o non disponibile.');
      const blob=await response.blob();if(abort.signal.aborted||generation!==imageGeneration.current)return;
      const row=references.find(item=>item.id===id);if(!row||Date.parse(row.expires_at)<=Date.now())throw new Error('Reference scaduta.');
      blobUrl.current=URL.createObjectURL(blob);selectedRef.current=id;setImage(blobUrl.current);setSelected(id);
    }catch(err){if(!abort.signal.aborted){clearImage();setError(err instanceof Error?err.message:'Preview non disponibile.');}}
    finally{if(!abort.signal.aborted)setBusy(false);}
  }
  async function revoke(){
    const abort=controller.current;if(!connected||busy||!selected||!entity||!confirmed||confirmedName!==entity.name||!abort||abort.signal.aborted)return;
    setBusy(true);setError('');
    try {
      const response=await fetch('/api'+route+selected+'/delete',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},cache:'no-store',signal:abort.signal,body:JSON.stringify({confirmed_name:confirmedName,confirm_irreversible:true})});
      if(!response.ok)throw new Error('Revoca non confermata. Aggiorna le reference.');
      if(abort.signal.aborted)return;
      listGeneration.current+=1;setReferences(rows=>rows.filter(row=>row.id!==selected));clearImage();
    }catch(err){if(!abort.signal.aborted)setError(err instanceof Error?err.message:'Revoca non riuscita.');}
    finally{if(!abort.signal.aborted)setBusy(false);}
  }
  return <section className="reference-panel"><h2>{face?'Reference dei visi autorizzati':'Reference degli oggetti'}</h2><p>{face?'Visi che hai salvato con consenso al viso valido. La revoca della persona toglie accesso a tutte le sue reference. Una reference non identifica automaticamente la persona nel feed o nell’audio.':'Immagini che hai salvato esplicitamente per il riconoscimento futuro. Una reference non dimostra ancora l’identità fisica o la posizione dell’oggetto.'}</p>
    <label htmlFor={face?'face-reference-person':'reference-object'}>{face?'Persona con reference del viso':'Oggetto con reference'}</label><select id={face?'face-reference-person':'reference-object'} disabled={!connected||busy} value={entityId} onChange={event=>setEntityId(event.target.value)}><option value="">{face?'Scegli una persona autorizzata':'Scegli un oggetto'}</option>{objects.map(item=><option key={item.id} value={item.id}>{item.name}</option>)}</select>
    {connected&&entityId&&!references.length&&<p>Nessuna reference attiva per {face?'questa persona':'questo oggetto'}.</p>}
    <p>Salva più viste distinte. I controlli di qualità segnalano immagini da rivedere; non certificano nitidezza, diversità delle viste o identità.</p>
    <ul>{references.map((row,index)=><li key={row.id}><span>Reference {index+1} · Scadenza: {new Date(row.expires_at).toLocaleString()}<small>{describeQuality(row.quality)}</small></span><button type="button" disabled={!connected||busy} onClick={()=>void show(row.id)}>Mostra reference {index+1}</button></li>)}</ul>
    {image&&<><img className="reference-image" src={image} alt={(face?'Reference del viso di ':'Reference salvata di ')+entity?.name}/><button className="secondary" type="button" onClick={clearImage}>Nascondi reference</button><form onSubmit={event=>{event.preventDefault();void revoke();}}><p>Revoca l’accesso e cancella questa reference. {face?'La persona resta registrata.':'L’oggetto resta nel catalogo.'} L’audit resta; la cancellazione è irreversibile.</p><label htmlFor={face?'face-reference-delete-name':'reference-delete-name'}>Riscrivi il nome {face?'della persona':'dell’oggetto'}: {entity?.name}</label><input id={face?'face-reference-delete-name':'reference-delete-name'} value={confirmedName} onChange={event=>setConfirmedName(event.target.value)} autoComplete="off" maxLength={4096}/><label className="check"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)}/>Confermo la cancellazione irreversibile della reference</label><button disabled={!connected||busy||!confirmed||confirmedName!==entity?.name}>Revoca e cancella reference</button></form></>}
    {error&&<p className="error" role="alert">{error}</p>}
  </section>;
}
