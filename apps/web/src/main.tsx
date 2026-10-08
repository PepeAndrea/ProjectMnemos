import React, { useState, useRef } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import { CapturePanel } from './CapturePanel';
import { ReminderPanel } from './ReminderPanel';
import { ReferencePanel } from './ReferencePanel';
import { PeoplePanel, type Person } from './PeoplePanel';

type Entity = { id:string; kind:string; name:string; aliases:string[]; confidence:number; enrolled:boolean; provenance:{source_id:string;method:string;observed_at:string}; retention:{scope:string;purpose:string} };

function EntityControls({entity,disabled,mutate}:{entity:Entity;disabled:boolean;mutate:(path:string,method:string,body:unknown)=>Promise<void>}) {
  const [newName,setNewName]=useState(entity.name);
  const [confirmedName,setConfirmedName]=useState('');
  const [confirmed,setConfirmed]=useState(false);
  return <details className="entity-controls"><summary>Gestisci {entity.name}</summary>
    <form onSubmit={e=>{e.preventDefault();void mutate('/entities/'+entity.id,'PUT',{...entity,name:newName.trim()});}}>
      <label htmlFor={'rename-'+entity.id}>Nuovo nome</label><div className="row"><input id={'rename-'+entity.id} value={newName} onChange={e=>setNewName(e.target.value)} maxLength={4096} required/><button disabled={disabled||!newName.trim()||newName.trim()===entity.name}>Salva nome</button></div>
    </form>
    <form onSubmit={e=>{e.preventDefault();void mutate('/entities/'+entity.id+'/delete','POST',{confirmed_name:confirmedName,confirm_irreversible:confirmed});}}>
      <p>La cancellazione elimina l’entità dal catalogo ed è irreversibile. Rimane l’audit dell’azione. Eventuali evidenze collegate richiedono il percorso dedicato di revoca.</p>
      <label htmlFor={'delete-'+entity.id}>Riscrivi il nome esatto: {entity.name}</label><input id={'delete-'+entity.id} value={confirmedName} onChange={e=>setConfirmedName(e.target.value)} autoComplete="off" maxLength={4096}/>
      <label className="check"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)}/>Confermo la cancellazione irreversibile</label>
      <button disabled={disabled||!confirmed||confirmedName!==entity.name}>Elimina entità</button>
    </form>
  </details>;
}

function App() {
  const authGeneration=useRef(0);
  const renderGeneration=authGeneration.current;
  const [token,setToken] = useState('');
  const [entities,setEntities] = useState<Entity[]>([]);
  const [people,setPeople] = useState<Person[]>([]);
  const [status,setStatus] = useState('Disconnesso');
  const [error,setError] = useState('');
  const [name,setName] = useState('');
  const [busy,setBusy] = useState(false);
  async function request<T>(path:string, method='GET', body?:unknown):Promise<T> {
    const response = await fetch('/api'+path,{method,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined,cache:'no-store'});
    if(!response.ok) {
      if(response.status===401) throw new Error('Token non valido.');
      if(response.status===503) throw new Error('Core o database non disponibile. Verifica il runtime.');
      throw new Error('Operazione non riuscita ('+response.status+').');
    }
    return response.json();
  }
  async function refresh() {
    if(renderGeneration!==authGeneration.current) return;
    setBusy(true); setError('');
    try { await request('/ready'); const values=await request<Entity[]>('/entities'); if(renderGeneration!==authGeneration.current) return;setEntities(values);setStatus('Connesso · memoria locale'); }
    catch(e) {if(renderGeneration!==authGeneration.current) return;setError(e instanceof Error?e.message:'Connessione fallita.'); setStatus('Disconnesso'); setEntities([]);}
    finally {setBusy(false);}
  }
  async function enroll(event:React.FormEvent) {
    event.preventDefault(); if(!name.trim()) return;
    setBusy(true); setError('');
    try {
      await request('/entities','POST',{kind:'object',name:name.trim(),aliases:[],confidence:1,enrolled:true,provenance:{source_id:'owner-dashboard',method:'human',observed_at:new Date().toISOString()},retention:{scope:'persistent',purpose:'explicit object enrollment'}});
      setName(''); setEntities(await request<Entity[]>('/entities'));
    } catch(e) {setError(e instanceof Error?e.message:'Salvataggio fallito.');}
    finally {setBusy(false);}
  }
  async function mutateEntity(path:string,method:string,body:unknown) {
    setBusy(true);setError('');
    try {await request(path,method,body);setEntities(await request<Entity[]>('/entities'));}
    catch(e) {setError(e instanceof Error?e.message:'Modifica non riuscita.');}
    finally {setBusy(false);}
  }
  async function disconnect() {
    setBusy(true);setError('');
    try {
      if(status!=='Disconnesso') {
        const result=await request<{state:string;error?:string}>('/capture/stop','POST');
        if(result.state!=='stopped'&&result.state!=='idle') throw new Error(result.error||'Stop del sensore non confermato.');
      }
      authGeneration.current+=1;setToken('');setEntities([]);setPeople([]);setStatus('Disconnesso');
    } catch(e) {setError(e instanceof Error?e.message:'Stop non confermato. Usa Stop sensori prima di disconnetterti.');}
    finally {setBusy(false);}
  }
  return <main>
    <header><div><span className="eyebrow">PROJECT MNEMOS</span><h1>La memoria di Tobi.</h1><p>Il tuo contesto, custodito sul tuo Mac.</p></div><span className="status" role="status">{status}</span></header>
    <section className="connection"><div><h2>Connetti il core locale</h2><p>Inserisci il token proprietario della tua installazione.</p></div><form onSubmit={e=>{e.preventDefault();void refresh();}}><label htmlFor="token">Token proprietario</label><div className="row"><input id="token" type="password" autoComplete="off" value={token} disabled={busy||status!=="Disconnesso"} onChange={e=>{authGeneration.current+=1;setToken(e.target.value);setStatus("Disconnesso");setEntities([]);}} required minLength={32}/><button disabled={busy}>Connetti</button><button className="secondary" type="button" onClick={()=>void disconnect()} disabled={busy}>Disconnetti</button></div></form></section>
    {error&&<p className="error" role="alert">{error}</p>}
    <CapturePanel token={token} connected={status!=="Disconnesso"} onEnrolled={refresh} objects={entities.filter(entity=>entity.kind==='object'&&entity.enrolled)} people={people}/>
    <div className="grid"><section><div className="section-title"><h2>Oggetti personali</h2><button className="secondary" disabled={busy||!token} onClick={()=>void refresh()}>Aggiorna</button></div><p>Registra un nome per gli oggetti che vuoi ricordare.</p><form onSubmit={enroll}><label htmlFor="name">Nome dell’oggetto</label><div className="row"><input id="name" value={name} onChange={e=>setName(e.target.value)} placeholder="Il mio zaino" maxLength={4096} required/><button disabled={busy||status==='Disconnesso'}>Memorizza</button></div></form><ul>{entities.filter(entity=>entity.kind!=='person').map(entity=><li className="entity-row" key={entity.id}><div><strong>{entity.name}</strong><small>{entity.provenance.method==='human'?'Registrato da te':'Sorgente: '+entity.provenance.source_id}</small></div><span>{entity.provenance.method==='human'?'Nome confermato':Math.round(entity.confidence*100)+'%'}</span><EntityControls entity={entity} disabled={busy||status==='Disconnesso'} mutate={mutateEntity}/></li>)}</ul>{!entities.length&&<p className="empty">Gli oggetti registrati compariranno qui.</p>}</section>
    <aside><h2>Privacy</h2><p>Camera e microfono richiedono consenso esplicito e possono essere fermati nel pannello sensori. Nessuna registrazione persistente è attiva.</p><p>Le persone richiedono un percorso di enrollment con consenso dedicato.</p><div className="note">Il feed mostra classi e track temporanei. Il catalogo conserva i nomi registrati; l’identità fisica e la posizione richiedono evidenze verificate.</div></aside></div>
    <ReferencePanel token={token} connected={status!=="Disconnesso"} objects={entities.filter(entity=>entity.kind==='object'&&entity.enrolled)}/>
    <PeoplePanel token={token} connected={status!=="Disconnesso"} onLoaded={setPeople}/>
    <ReferencePanel kind="face" token={token} connected={status!=="Disconnesso"} objects={people.filter(person=>person.face&&Date.parse(person.expires_at)>Date.now()).map(person=>({...person,kind:'person'}))}/>
    <ReminderPanel token={token} connected={status!=="Disconnesso"}/>
    <footer>Mnemos · Tobi · Local-first</footer>
  </main>;
}
createRoot(document.getElementById('root')!).render(<App/>);
