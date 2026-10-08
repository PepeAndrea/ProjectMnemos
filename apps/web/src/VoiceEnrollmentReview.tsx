import {useState} from 'react';

export type EnrollmentProposal = {id:string;utterance_id:string;suggested_name:string;confidence:number;state:string;requires_owner_review:boolean;policy:{allowed:boolean;reason:string}};
export type PersonVoiceConsent = {face:boolean;voice:boolean;subject_permission_attested:boolean;expires_at:string};

export function VoiceEnrollmentReview({proposal,disabled,onReview}:{proposal:EnrollmentProposal;disabled:boolean;onReview:(id:string,action:'approve'|'reject',name?:string,person?:PersonVoiceConsent)=>Promise<void>}) {
  const [name,setName]=useState(proposal.suggested_name);
  const [kind,setKind]=useState<'object'|'person'>('object');
  const [confirmed,setConfirmed]=useState(false);
  const [face,setFace]=useState(false);
  const [voice,setVoice]=useState(false);
  const [attested,setAttested]=useState(false);
  const [expiry,setExpiry]=useState('');
  const deadline=expiry?new Date(expiry):undefined;
  const consentValid=(face||voice)&&attested&&deadline&&Number.isFinite(deadline.getTime())&&deadline.getTime()>Date.now();
  const valid=confirmed&&name.trim()&&(kind==='object'||consentValid);
  function submit(){
    if(disabled||proposal.state!=='pending'||!valid)return;
    void onReview(proposal.id,'approve',name.trim(),kind==='person'?{face,voice,subject_permission_attested:attested,expires_at:deadline!.toISOString()}:undefined);
  }
  return <form className="voice-enrollment" onSubmit={event=>{event.preventDefault();submit();}}>
    <h4>Proposta vocale da rivedere</h4><p>Il parlante è anonimo. Verifica e correggi il nome; la trascrizione non autorizza registrazioni o comandi.</p>
    <label htmlFor={'voice-kind-'+proposal.id}>Tipo di registrazione</label><select id={'voice-kind-'+proposal.id} value={kind} disabled={disabled||proposal.state!=='pending'} onChange={event=>{setKind(event.target.value as 'object'|'person');setConfirmed(false);setFace(false);setVoice(false);setAttested(false);setExpiry('');}}><option value="object">Oggetto</option><option value="person">Persona autorizzata</option></select>
    <label htmlFor={'voice-name-'+proposal.id}>Nome proposto · puoi correggerlo</label><input id={'voice-name-'+proposal.id} value={name} onChange={event=>{setName(event.target.value);setConfirmed(false);}} maxLength={4096} required disabled={disabled||proposal.state!=='pending'}/>
    {kind==='person'&&<><p>Registra il consenso esplicito della persona. Viso e voce sono permessi separati; i campioni hanno un percorso dedicato. Questi permessi non autorizzano comandi o registrazioni di conversazioni.</p><fieldset disabled={disabled||proposal.state!=='pending'}><legend>Consenso della persona proposta</legend><label className="check"><input type="checkbox" checked={face} onChange={event=>setFace(event.target.checked)}/>Consenso al viso della persona proposta</label><label className="check"><input type="checkbox" checked={voice} onChange={event=>setVoice(event.target.checked)}/>Consenso alla voce della persona proposta</label><label htmlFor={'voice-person-expiry-'+proposal.id}>Scadenza del consenso proposto · ora locale</label><input id={'voice-person-expiry-'+proposal.id} type="datetime-local" value={expiry} onInput={event=>setExpiry(event.currentTarget.value)} onChange={event=>setExpiry(event.target.value)} required/><label className="check"><input type="checkbox" checked={attested} onChange={event=>setAttested(event.target.checked)}/>Attesto il consenso esplicito della persona proposta per i trattamenti selezionati</label></fieldset></>}
    <label className="check"><input type="checkbox" checked={confirmed} onChange={event=>setConfirmed(event.target.checked)} disabled={disabled||proposal.state!=='pending'}/>Confermo di voler registrare questo nome nel catalogo</label>
    <div className="row"><button disabled={disabled||proposal.state!=='pending'||!valid}>{kind==='person'?'Registra persona proposta e consenso':'Registra nome'}</button><button type="button" className="secondary" disabled={disabled||proposal.state!=='pending'} onClick={()=>void onReview(proposal.id,'reject')}>Ignora proposta</button></div>
    <small>La proposta scade con lo stop o la fine della sessione e comunque entro cinque minuti.</small>
  </form>;
}
