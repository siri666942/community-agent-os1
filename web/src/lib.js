export const statusLabel = status => ({
  PASS:'审核通过', REVIEW_REQUIRED:'待人工复核', PENDING:'待审批',
  APPROVED:'已批准', REJECTED:'已打回', SIMULATED_APPROVAL:'模拟批准',
  READY:'已批准，待人工执行', INCOMPLETE:'未完成', PENDING_APPROVAL:'待审批',
  PLANNED:'已规划', WAITING_CONTENT:'待生成', HUMAN_REVIEW:'人工复核',
  PAUSED:'暂停触达', DRAFT:'本地草稿', SIMULATED_DELIVERY:'模拟送达',
  COMPLETE:'已完成'
})[status] || status || '未知';

export function approvalItems(data, workflow) {
  const tickets=data?.tickets||[],packages=data?.packages||[];
  return [
    ...tickets.filter(t=>t.gate7==='PENDING'||t.gate7==='SIMULATED_APPROVAL'||
      t.human_task?.status==='PENDING'||(t.human_task?.status!=='COMPLETED'&&
      t.review?.status&&t.review.status!=='PASS')).map(t=>({
        ...t,kind:'ticket',
        status:t.gate7==='PENDING'?'PENDING':t.review?.status&&t.review.status!=='PASS'?'REVIEW_REQUIRED':t.human_task?.status==='PENDING'?'HUMAN_REVIEW':t.gate7,
        title:'工单 '+t.id,summary:t.message,reason:t.human_task?.reason||t.risk_reason,
        advice:t.escalation,content:t.review_candidate,
        content_hash:t.content_hash||t.gate7_decision?.content_hash
      })),
    ...(workflow?.artifacts||[]).filter(a => a.material_hash && a.review?.status === 'PASS' && !(workflow?.approvals||[]).some(x => x.batch_id === a.batch_id && x.material_hash === a.material_hash)).map(a => ({
      ...a, id: a.id, kind: 'growth', title: '客户跟进计划', status: 'PENDING', summary: '审核跟进内容和完整名单',
      content: a.content, recipients: a.approval_recipients
    })),
    ...packages.filter(p=>p.status==='PENDING_APPROVAL').map(p=>({
      ...p,kind:'package',title:'运营包 '+p.day,summary:p.day,content_hash:p.content_hash
    }))
  ];
}

export function packageMaterial(pkg) {
  const tasks=pkg?.tasks;
  if(!Array.isArray(tasks)||!tasks.length||tasks.some(t=>!t.task||!t.review||
    ['time','channel','audience','source'].some(k=>typeof t.task[k]!=='string')||
    typeof t.review.status!=='string'||typeof t.review.content!=='string')) return null;
  return tasks.map((t,i)=>
    '## 任务 '+(i+1)+' · '+t.task.time+' / '+t.task.channel+' / '+t.task.audience+
    '\n来源: '+t.task.source+' | 审核: '+t.review.status+'\n\n'+t.review.content
  ).join('\n\n');
}

export async function request(path,body) {
  const init=body===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)};
  const response=await fetch(path,init);
  let data;
  try{data=await response.json();}catch{throw Error('服务返回了无法解析的数据');}
  if(!response.ok)throw Error(data.detail||data.error||'请求失败 ('+response.status+')');
  return data;
}

export async function resolveJob(result) {
  if(!result?.job_id)return result;
  const job=result.job_id;
  for(;;){
    await new Promise(resolve=>setTimeout(resolve,1000));
    const current=await request('/api/jobs/'+encodeURIComponent(job));
    if(current.status==='failed')throw Error(current.error||'任务执行失败');
    if(current.status==='completed')return current.result;
  }
}
