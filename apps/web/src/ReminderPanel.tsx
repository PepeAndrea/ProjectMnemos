import {useEffect,useState} from 'react';

type Reminder = {id:string;text:string;state:string;trigger:{due_at:string}};
type Notification = {reminder_id:string;text:string;created_at:string};

export function ReminderPanel({token,connected}:{token:string;connected:boolean}) {
  const [text,setText]=useState('');
  const [due,setDue]=useState('');
  const [reminders,setReminders]=useState<Reminder[]>([]);
  const [notifications,setNotifications]=useState<Notification[]>([]);
  const [error,setError]=useState('');
  const [busy,setBusy]=useState(false);
  useEffect(()=>{
    const abort=new AbortController();let pending=false;
    setReminders([]);setNotifications([]);setError('');setText('');setDue('');
    if(!connected) return ()=>abort.abort();
    async function poll() {
      if(pending||abort.signal.aborted)return;
      pending=true;
      try {
        const headers={Authorization:'Bearer '+token};
        const responses=await Promise.all(['/reminders','/notifications','/scheduler/status'].map(path=>fetch('/api'+path,{headers,cache:'no-store',signal:abort.signal})));
        if(responses.some(response=>!response.ok))throw new Error('Promemoria locali non disponibili.');
        const [items,inbox,status]=await Promise.all(responses.map(response=>response.json()));
        if(abort.signal.aborted)return;
        setReminders(items);setNotifications(inbox);setError(status.error||'');
      } catch(e) {if(!abort.signal.aborted)setError(e instanceof Error?e.message:'Collegamento interrotto.');}
      finally {pending=false;}
    }
    void poll();const timer=window.setInterval(()=>void poll(),1000);
    return ()=>{abort.abort();window.clearInterval(timer);};
  },[token,connected]);
  async function create(event:React.FormEvent) {
    event.preventDefault();setBusy(true);setError('');
    try {
      const date=new Date(due);
      if(!text.trim()||!Number.isFinite(date.getTime()))throw new Error('Inserisci testo e data validi.');
      const response=await fetch('/api/reminders',{method:'POST',headers:{Authorization:'Bearer '+token,'Content-Type':'application/json'},body:JSON.stringify({text:text.trim(),trigger:{due_at:date.toISOString()},provenance:{source_id:'owner-dashboard',method:'human',observed_at:new Date().toISOString()}})});
      if(!response.ok)throw new Error('Salvataggio del promemoria fallito.');
      setText('');setDue('');
    } catch(e) {setError(e instanceof Error?e.message:'Operazione fallita.');}
    finally {setBusy(false);}
  }
  return <section>
    <h2>Promemoria di Tobi</h2><p>La scadenza genera una notifica in questa pagina. I promemoria restano sul Mac e riprendono al riavvio del core.</p>
    <form onSubmit={event=>void create(event)}><label htmlFor="reminder-text">Cosa vuoi ricordare</label><input id="reminder-text" value={text} onChange={event=>setText(event.target.value)} required maxLength={4096} disabled={!connected||busy}/><label htmlFor="reminder-due">Quando · ora locale</label><div className="row"><input id="reminder-due" type="datetime-local" value={due} onChange={event=>setDue(event.target.value)} required disabled={!connected||busy}/><button disabled={!connected||busy}>Crea promemoria</button></div></form>
    {error&&<p className="error" role="alert">{error}</p>}
    <div aria-live="polite">{notifications.length>0&&<h3>Notifiche locali</h3>}<ul>{notifications.map(item=><li key={item.reminder_id}><strong>{item.text}</strong><small>{new Date(item.created_at).toLocaleString('it-IT')}</small></li>)}</ul></div>
    <ul>{reminders.filter(item=>item.state==='pending').map(item=><li key={item.id}><strong>{item.text}</strong><small>{new Date(item.trigger.due_at).toLocaleString('it-IT')}</small></li>)}</ul>
  </section>;
}
