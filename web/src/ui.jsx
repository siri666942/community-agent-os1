import { ArrowRight, AlertCircle, RefreshCw } from 'lucide-react';
import { statusLabel } from './lib';

export function PageHeading({ kicker, title, description, action }) {
  return <div className="page-heading"><div><div className="page-eyebrow">{kicker}</div><h1>{title}</h1><p>{description}</p></div>{action&&<div className="page-heading-action">{action}</div>}</div>;
}
export function Panel({ title, description, children, className='' }) {
  return <section className={'panel '+className}><div className="panel-title"><h2>{title}</h2>{description&&<p>{description}</p>}</div>{children}</section>;
}
export function Empty({ title, description }) {
  return <div className="empty"><strong>{title}</strong><p>{description}</p></div>;
}
export function Metric({ title, value, hint, icon:Icon }) {
  return <div className="metric-card"><div className="metric-label">{title}<Icon size={19} strokeWidth={1.7}/></div><strong>{value}</strong><small>{hint}</small></div>;
}
export function StatusBadge({ status }) {
  const kind=['REJECTED','PAUSED'].includes(status)?'danger':['PENDING','REVIEW_REQUIRED','PENDING_APPROVAL','SIMULATED_APPROVAL','INCOMPLETE','HUMAN_REVIEW'].includes(status)?'warning':'default';
  return <span className={'status-badge '+kind}>{statusLabel(status)}</span>;
}
export function Block({ title, value }) {
  return <div className="detail-block"><h3>{title}</h3><div className="prose">{value||'暂无'}</div></div>;
}
export function Interrupted({ kind, ctx }) {
  const rows=(ctx.data?.interrupted_artifacts||[]).filter(x=>x.kind===kind);
  if(!rows.length)return null;
  const retry=item=>{
    if(kind==='ticket'&&item.message)ctx.run('/api/service',{message:item.message,customer_id:item.customer_id||''},r=>ctx.setTicket(r.ticket||r));
    if(kind==='package'&&item.day)ctx.run('/api/sop',{day:item.day},r=>{const p=r.package||r;ctx.setPackageRecord({...p,id:p.id||(p.path||'').split(/[\\/]/).pop().replace(/\.md$/,'')})});
  };
  return <section className="interrupted"><h2>中断的历史产物</h2><Panel title="隔离记录" description="这些记录不进入审批或交付，可以从原始输入重新运行。">{rows.map((item,i)=><div className="record" key={item.id||item.run_id||i}><div className="record-head"><strong>{item.id||item.run_id}</strong><StatusBadge status="INCOMPLETE"/></div><p>{kind==='ticket'?item.message:item.day}</p><button className="button outline" disabled={ctx.busy||!(kind==='ticket'?item.message:item.day)} onClick={()=>retry(item)}><RefreshCw size={15}/> 重新运行</button></div>)}</Panel></section>;
}
