import {useEffect,useRef,useState} from 'react';

export type Person={id:string;name:string;face:boolean;voice:boolean;expires_at:string;assurance:string};
function PersonControls({person,busy,mutate}:{person:Person;busy:boolean;mutate:(path:string,method:string,body:unknown)=>Promise<void>}) {
  const [name,setName]=useState(person.name);
  const [confirmation,setConfirmation]=useState('');
  const [confirmed,setConfirmed]=useState(false);
  return <details className="entity-controls"><summary>Gestisci {person.name}</summary>
    <form onSubmit={e=>{e.preventDefault();if(!busy&&name.trim()) void mutate('/people/'+person.id+'/name','PUT',{name:name.trim()});}}><label htmlFor={'person-name-'+person.id}>Nuovo nome</label><div className="row"><input id={'person-name-'+person.id} value={name} onChange={e=>setName(e.target.value)} maxLength={4096}/><button disabled={busy||!name.trim()||name.trim()===person.name}>Salva nome</button></div></form>
    <form onSubmit={e=>{e.preventDefault();if(confirmed&&!busy&&confirmation===person.name) void mutate('/people/'+person.id+'/revoke','POST',{confirmed_name:confirmation,confirm_irreversible:true});}}>
      <p>Revoca il consenso e cancella identità e campioni biometrici dell’installazione. Rimangono i riferimenti di audit. La cancellazione è irreversibile.</p><label htmlFor={'person-revoke-'+person.id}>Riscrivi il nome esatto: {person.name}</label><input id={'person-revoke-'+person.id} value={confirmation} onChange={e=>setConfirmation(e.target.value)} maxLength={4096}/><label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Confermo revoca e cancellazione</label><button disabled={busy||!confirmed||confirmation!==person.name}>Revoca e cancella persona</button>
    </form>
  </details>;
}
export function PeoplePanel({token,connected,onLoaded}:{token:string;connected:boolean;onLoaded?:(people:Person[])=>void}) {
  const [people,setPeople]=useState<Person[]>([]);
  const requestAbort=useRef(new AbortController());
  const [name,setName]=useState('');
  const [face,setFace]=useState(false);
  const [voice,setVoice]=useState(false);
  const [attested,setAttested]=useState(false);
  const [expires,setExpires]=useState('');
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState('');
  async function load(signal?:AbortSignal) {
    const response=await fetch('/api/people',{headers:{Authorization:'Bearer '+token},cache:'no-store',signal});
    if(!response.ok) throw new Error('Registro delle persone non disponibile.');
    const entities:Person[]=await response.json();
    if(!signal?.aborted) {setPeople(entities);onLoaded?.(entities);}
  }
  useEffect(()=>{
    const abort=new AbortController();
    requestAbort.current=abort;
    setBusy(false);
    setPeople([]);onLoaded?.([]);setName('');setFace(false);setVoice(false);setAttested(false);setExpires('');setError('');
    let pending=false;
    async function poll() {if(pending||abort.signal.aborted) return;pending=true;try {await load(abort.signal);} catch(e) {if(!abort.signal.aborted) {setPeople([]);onLoaded?.([]);setError(e instanceof Error?e.message:'Connessione interrotta.');}} finally {pending=false;}}
    if(connected) void poll();
    const timer=connected?window.setInterval(()=>void poll(),1000):undefined;
    return()=>{abort.abort();if(timer) window.clearInterval(timer);};
  },[token,connected]);
  async function mutate(path:string,method:string,body:unknown) {
    const signal=requestAbort.current.signal;
    if(signal.aborted||!connected) return;
    setBusy(true);setError('');
    try {
      const response=await fetch('/api'+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify(body),cache:'no-store',signal});
      if(!response.ok) throw new Error(response.status===403?'Consenso o conferma non validi.':'Operazione non riuscita. Aggiorna il registro prima di riprovare.');
      if(signal.aborted) return;
      await load(signal);
      if(path==='/people') {setName('');setFace(false);setVoice(false);setAttested(false);setExpires('');}
    } catch(e) {if(!signal.aborted) setError(e instanceof Error?e.message:'Operazione fallita.');}
    finally {if(!signal.aborted) setBusy(false);}
  }
  return <section className="people-panel"><div className="section-title"><h2>Persone autorizzate</h2><button className="secondary" disabled={!connected||busy} onClick={()=>void load(requestAbort.current.signal).catch(e=>{if(!requestAbort.current.signal.aborted) setError(e.message);})}>Aggiorna persone</button></div>
    <p>Registra la tua attestazione del consenso esplicito della persona. Viso e voce hanno permessi separati; i campioni si acquisiscono nel percorso dedicato. Questi permessi non autorizzano comandi o registrazioni di conversazioni.</p>
    <form onSubmit={e=>{e.preventDefault();if(connected&&!busy&&attested&&(face||voice)&&name.trim()&&expires) void mutate('/people','POST',{name:name.trim(),face,voice,subject_permission_attested:attested,expires_at:new Date(expires).toISOString()});}}>
      <label htmlFor="person-enroll-name">Nome della persona autorizzata</label><input id="person-enroll-name" value={name} onChange={e=>setName(e.target.value)} disabled={!connected||busy} maxLength={4096} required/>
      <fieldset><legend>Consenso al riconoscimento locale</legend><label className="check"><input type="checkbox" checked={face} onChange={e=>setFace(e.target.checked)} disabled={!connected||busy}/>Viso</label><label className="check"><input type="checkbox" checked={voice} onChange={e=>setVoice(e.target.checked)} disabled={!connected||busy}/>Voce</label></fieldset>
      <label htmlFor="person-consent-expiry">Scadenza del consenso · ora locale</label><input id="person-consent-expiry" type="datetime-local" value={expires} onChange={e=>setExpires(e.target.value)} onInput={e=>setExpires(e.currentTarget.value)} disabled={!connected||busy} required/>
      <label className="check"><input type="checkbox" checked={attested} onChange={e=>setAttested(e.target.checked)} disabled={!connected||busy}/>Attesto di avere il consenso esplicito della persona per i trattamenti selezionati</label><button disabled={!connected||busy||!attested||(!face&&!voice)||!name.trim()||!expires}>Registra persona e consenso</button>
    </form><ul>{people.map(person=><li className="entity-row" key={person.id}><div><strong>{person.name}</strong><small>Consenso attestato · Viso: {person.face?'sì':'no'} · Voce: {person.voice?'sì':'no'} · Scadenza: {new Date(person.expires_at).toLocaleString()}</small></div><PersonControls person={person} busy={busy||!connected} mutate={mutate}/></li>)}</ul>{!people.length&&<p className="empty">Nessuna persona registrata.</p>}{error&&<p className="error" role="alert">{error}</p>}
  </section>;
}
