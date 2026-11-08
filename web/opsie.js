/* Opsie: per-tab identities and one server-backed message state. */
const $ = s => document.querySelector(s);
const esc = x => String(x ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const state = {token:sessionStorage.getItem('opsie.token'), user:null, conversations:[], cid:null, messages:[], target:null,
  job:null, jobTimer:null, drafts:[], selected:null, profile:null, dashboard:null, page:'chat', full:false, renderKey:'', loading:null, pending:[]};
let toastTimer;
let dashboardRequest=null;
function dashboardCacheKey(){return 'opsie.dashboard.'+state.user.user_id}
function toast(message){const el=$('#toast');el.textContent=message;el.classList.remove('hidden');clearTimeout(toastTimer);toastTimer=setTimeout(()=>el.classList.add('hidden'),4000);}
async function api(path, options={}){
  const headers={'Content-Type':'application/json'}; if(state.token) headers.Authorization='Bearer '+state.token;
  const response=await fetch(path,{...options,headers:{...headers,...(options.headers||{})}});
  let data={};try{data=await response.json()}catch{}
  if(!response.ok){const error=new Error(data.error||'请求失败');error.status=response.status;error.data=data;throw error}return data;
}
function post(path, data){return api(path,{method:'POST',body:JSON.stringify(data)});}
function showPage(page){
  if(state.user?.role==='parent' && page!=='chat') return;
  state.page=page;document.querySelectorAll('.page').forEach(el=>el.classList.add('hidden'));$('#page-'+page).classList.remove('hidden');
  document.querySelectorAll('.nav').forEach(el=>el.classList.toggle('active',el.dataset.page===page));
  $('#page-title').textContent=({workspace:'工作台',chat:state.user.role==='parent'?'阅读营消息':'客户对话',profiles:'用户画像',sop:'SOP 流程',rules:'话术与质检'})[page];
  if(page==='workspace'||page==='profiles') loadDashboard();
  if(page==='sop') loadSop();
  if(page==='rules') api('/api/v1/policy').then(renderPolicy).catch(e=>toast(e.message));
}
async function loadSop(){
  try{const data=await api('/api/v1/sop');$('#sop-content').innerHTML=Object.entries(data.days).map(([day,entries])=>
    `<details><summary><b>${esc(day)}</b> · ${entries.length} 项</summary>${entries.map(e=>`<div class="profile-section"><strong>${esc(e.time||'运营安排')}</strong><p>${esc(e.scene||'')} ${esc(e.target||'')}</p>${(Array.isArray(e.scripts)?e.scripts:[]).map(s=>`<p class="sop-script">${esc(s)}</p>`).join('')}${e.note?`<p>${esc(e.note)}</p>`:''}</div>`).join('')}</details>`).join('')}
  catch(e){$('#sop-content').textContent='暂时无法加载 SOP：'+e.message}
}
function renderPolicy(p){
  const labels={'product.catalog':'产品与权益','product.pricing':'价格','product.promotions':'优惠活动','refund.policy':'退费规则','product.access_after_expiry':'到期后使用','product.assessment_trial':'测评与试听','product.teacher_service':'老师服务'};
  const valueText=v=>typeof v==='string'?v:Array.isArray(v)?v.map(valueText).join('；'):v&&typeof v==='object'?Object.entries(v).map(([k,x])=>`${k}：${valueText(x)}`).join('；'):String(v??'');
  $('#policy-content').innerHTML=Object.entries(labels).map(([key,label])=>{const entry=p.product[key];return `<p><b>${esc(label)}：</b>${entry?.status==='confirmed'&&entry.value!==null?esc(valueText(entry.value)):'待确认'}</p>`}).join('');
  $('#policy-version').textContent='当前口径版本 '+p.version;
}
function start(user){
  state.user=user;$('#login-screen').classList.add('hidden');$('#app').classList.remove('hidden');
  if(user.role==='teacher')try{const saved=JSON.parse(localStorage.getItem(dashboardCacheKey()));if(saved?.data?.profiles){state.dashboard=saved.data;renderDashboard();renderProfiles();$('#dashboard-status').textContent='显示本机缓存，正在更新…'}}catch{}
  const teacher=user.role==='teacher';document.querySelectorAll('.teacher-only').forEach(el=>el.classList.toggle('hidden',!teacher));
  $('.chat-layout').classList.toggle('parent',!teacher);$('#self-name').textContent=user.display_name;$('#self-role').textContent=teacher?'运营老师':'家长';$('#self-avatar').textContent=user.display_name.slice(0,1);
  if(!teacher){document.querySelector('[data-page="chat"] span').textContent='我的消息';$('#message-input').placeholder='给老师或群里发消息…'}
  showPage(teacher?'workspace':'chat');loadConversations().catch(e=>toast(e.message));
}
$('#login-form').addEventListener('submit',async event=>{
  event.preventDefault();const btn=event.submitter;btn.disabled=true;$('#login-error').textContent='';
  try{const result=await post('/api/v1/login',{username:$('#username').value.trim(),password:$('#password').value});state.token=result.token;sessionStorage.setItem('opsie.token',state.token);$('#password').value='';start(result.user)}
  catch(e){$('#login-error').textContent=e.message}finally{btn.disabled=false}
});
$('#logout').onclick=async()=>{try{await post('/api/v1/logout',{})}catch{}sessionStorage.removeItem('opsie.token');location.reload()};
document.querySelectorAll('.nav').forEach(button=>button.onclick=()=>showPage(button.dataset.page));

async function loadConversations(){
  const data=await api('/api/v1/conversations');state.conversations=data.items;renderConversations();
  if(!state.cid&&state.conversations.length){const initial=state.conversations.find(c=>c.type==='direct')||state.conversations[0];await openConversation(initial.id,false)}
}
function renderConversations(){
  const query=$('#search').value.trim().toLowerCase();
  $('#conversation-list').innerHTML=state.conversations.filter(c=>c.title.toLowerCase().includes(query)).map(c=>`<button class="conv ${c.id===state.cid?'active':''}" data-cid="${esc(c.id)}"><span class="avatar">${c.type==='group'?'群':esc(c.title.slice(0,1))}</span><span><strong>${esc(c.title)}</strong><small>${c.type==='group'?'阅读营群聊':'私聊'}</small></span></button>`).join('');
  document.querySelectorAll('[data-cid]').forEach(el=>el.onclick=()=>openConversation(el.dataset.cid));
}
$('#search').oninput=renderConversations;
async function openConversation(cid,navigate=true){
  if(state.cid===cid){if(navigate)showPage('chat');return}
  state.cid=cid;state.target=null;state.profile=null;state.drafts=[];state.job=null;state.full=false;state.selected=null;state.renderKey='';
  state.messages=[];$('#messages').innerHTML='<div class="empty">正在加载会话…</div>';$('#generate').disabled=false;
  clearTimeout(state.jobTimer);$('#message-input').value='';$('#draft-hint').textContent='选择一条家长消息，结合上下文生成建议。';$('#drafts').innerHTML='';$('#inbound-alert').classList.add('hidden');
  const c=state.conversations.find(x=>x.id===cid);$('#chat-title').textContent=c?.title||'会话';$('#chat-subtitle').textContent=c?.type==='group'?'群聊 · 点击家长消息选择回复对象':'一对一聊天';
  renderConversations();if(navigate)showPage('chat');await refreshMessages(true);if(state.cid!==cid)return;
  if(state.user.role==='teacher'){
    const target=[...state.messages].reverse().find(m=>m.sender_role==='parent'&&m.sender_id&&m.type==='text');
    if(target) await selectTarget(target.id,true);
  }
}
async function refreshMessages(force=false){
  if(!state.cid||(state.loading===state.cid&&!force))return;const cid=state.cid;state.loading=cid;
  try{
    const data=await api('/api/v1/messages/'+encodeURIComponent(cid)+(state.full?'?all=1':''));if(cid!==state.cid)return;
    const oldIds=new Set(state.messages.map(m=>m.id));const previousKey=state.renderKey;state.messages=data.items;const key=JSON.stringify(data.items.map(m=>[m.id,m.text,m.time]));
    if(force||key!==state.renderKey){state.renderKey=key;renderMessages(force)}
    if(previousKey&&key!==previousKey&&state.drafts.length){$('#draft-hint').textContent='会话已有新变化，建议重新生成。';renderDrafts(true)}
    const incoming=[...data.items].reverse().find(m=>!oldIds.has(m.id)&&m.sender_role==='parent'&&m.sender_id&&m.type==='text');
    if(previousKey&&incoming&&state.user.role==='teacher'&&!$('#message-input').value.trim())selectTarget(incoming.id,true);
    if(state.user.role==='teacher') loadInbound(cid);
  }catch(e){if(force)toast(e.message)}finally{if(state.loading===cid)state.loading=null}
}
function renderMessages(scroll){
  const stage=$('#messages');const nearBottom=stage.scrollHeight-stage.scrollTop-stage.clientHeight<100;
  stage.innerHTML=[...state.messages,...state.pending.filter(m=>m.cid===state.cid)].map(m=>{
    const mine=m.sender_id===state.user.user_id;const selectable=state.user.role==='teacher'&&m.sender_role==='parent'&&m.sender_id&&m.type==='text';
    return `<div class="message ${mine?'mine':''} ${selectable?'selectable':''} ${state.target===m.id?'selected':''}" ${selectable?`data-target="${esc(m.id)}"`:''}><span class="avatar">${esc((m.sender_name||'?').slice(0,1))}</span><div class="message-body"><div class="message-meta">${esc(m.sender_name)} · ${m.pendingStatus?esc(m.pendingStatus):esc(String(m.time).slice(5,16))} ${m.source==='历史群'?' · 历史':m.source==='演示初始私聊'?' · 演示':''}</div><div class="bubble">${esc(m.text)}</div>${m.failed?`<div><button type="button" class="retry-send" data-retry="${esc(m.id)}">重试</button> <button type="button" class="retry-send" data-edit="${esc(m.id)}">编辑</button></div>`:''}</div></div>`;
  }).join('')||'<div class="empty">还没有消息，打个招呼吧。</div>';
  stage.querySelectorAll('[data-target]').forEach(el=>el.onclick=()=>selectTarget(el.dataset.target,true));
  stage.querySelectorAll('[data-retry]').forEach(el=>el.onclick=()=>{const m=state.pending.find(x=>x.id===el.dataset.retry);if(m)sendPending(m)});
  stage.querySelectorAll('[data-edit]').forEach(el=>el.onclick=()=>{const m=state.pending.find(x=>x.id===el.dataset.edit);if(!m)return;if($('#message-input').value.trim()){toast('请先处理输入框中的文字');return}$('#message-input').value=m.text;state.pending=state.pending.filter(x=>x!==m);renderMessages(false);$('#message-input').focus()});
  if(scroll||nearBottom) stage.scrollTop=stage.scrollHeight;
}
$('#load-history').onclick=()=>{state.full=true;refreshMessages(true)};
async function selectTarget(key, generate=false){
  const cid=state.cid;const msg=state.messages.find(m=>m.id===key);if(!msg)return;
  const changed=state.target!==key;state.target=key;renderMessages(false);
  if(changed){state.drafts=[];state.selected=null;state.job=null;clearTimeout(state.jobTimer);$('#drafts').innerHTML='';$('#draft-hint').textContent='回复 '+msg.sender_name+' · '+msg.text.slice(0,30);}
  if(state.user.role==='teacher'){
    if(generate&&changed&&state.cid===cid&&state.target===key) generateDrafts();
    try{const p=await api('/api/v1/profile/'+encodeURIComponent(msg.sender_id));if(state.cid===cid&&state.target===key){state.profile=p;renderSideProfile()}}catch(e){toast(e.message)}
  }
}
async function loadInbound(cid){
  try{const data=await api('/api/v1/inbound/'+cid);if(cid!==state.cid)return;
    const r=data.items.find(x=>x.message_key===state.target);const alert=$('#inbound-alert');
    if(r&&r.status==='complete'&&r.is_sensitive){alert.textContent='质检提醒：'+(r.details?.reason||'家长的问题需要慎重处理');alert.classList.remove('hidden')}
    else if(r&&['pending','running'].includes(r.status)){alert.textContent='正在识别家长消息…';alert.classList.remove('hidden')}
    else if(r&&r.status==='failed'){alert.innerHTML='敏感识别暂不可用。 <button class="subtle" id="retry-inbound">重新识别</button>';alert.classList.remove('hidden');$('#retry-inbound').onclick=async()=>{try{await post('/api/v1/retry-inbound',{conversation_id:state.cid,message_id:state.target});loadInbound(state.cid)}catch(e){toast(e.message)}}}
    else alert.classList.add('hidden');
  }catch{}
}
$('#generate').onclick=()=>generateDrafts();
async function generateDrafts(){
  if(!state.target){toast('请先选择一条家长消息');return}
  const cid=state.cid,target=state.target;clearTimeout(state.jobTimer);state.job=null;state.drafts=[];renderDrafts();$('#draft-hint').textContent='正在阅读会话并生成三条建议…';$('#generate').disabled=true;
  try{const r=await post('/api/v1/drafts',{conversation_id:cid,target_message_id:target});if(cid!==state.cid||target!==state.target)return;state.job=r.job_id;pollJob(r.job_id,cid,target)}
  catch(e){if(cid===state.cid&&target===state.target){$('#draft-hint').textContent='生成失败：'+e.message;$('#generate').disabled=false}}
}
async function pollJob(job,cid,target,failures=0){
  if(job!==state.job||cid!==state.cid||target!==state.target)return;
  try{const r=await api('/api/v1/jobs/'+job);if(job!==state.job)return;
    if(['queued','running'].includes(r.status)){state.jobTimer=setTimeout(()=>pollJob(job,cid,target),2200);return}
    $('#generate').disabled=false;
    if(r.status==='succeeded'){state.drafts=r.result.drafts;$('#draft-hint').textContent=r.stale?'AI 实时生成 · 会话已有新变化，建议重新生成。':'AI 实时生成 · 已结合会话与画像，点击填入输入框';renderDrafts(r.stale)}
    else $('#draft-hint').textContent='AI 生成失败：'+(r.error||r.status)+'。可点击重新生成。';
  }catch(e){if(job!==state.job||cid!==state.cid||target!==state.target)return;if(failures<5){$('#draft-hint').textContent='连接暂时不稳定，正在继续获取 AI 结果…';state.jobTimer=setTimeout(()=>pollJob(job,cid,target,failures+1),3000)}else{$('#generate').disabled=false;$('#draft-hint').textContent='获取建议失败：'+e.message+'。可点击重新生成。'}}
}
function renderDrafts(stale=false){
  $('#drafts').innerHTML=state.drafts.map((d,i)=>{const q=d.qc||{};const label=q.status==='red'?'需修改':q.status==='yellow'?'需核对':q.status==='pending'?'候选质检暂不可用':'发送前再次质检';const reason=q.status==='red'||q.status==='yellow'?(q.suggestion||q.risks?.[0]?.type||''):'';return `<button type="button" class="draft ${state.selected===i?'selected':''}" data-draft="${i}"><b>${esc(d.variant)} · ${esc(d.position)}</b>${esc(d.text)}<em>${esc(label)}${reason?'：'+esc(reason):''}${stale?' · 建议已过期':''}</em></button>`}).join('');
  document.querySelectorAll('[data-draft]').forEach(button=>button.onclick=()=>{state.selected=Number(button.dataset.draft);$('#message-input').value=state.drafts[state.selected].text;$('#message-input').focus();renderDrafts(stale)});
}
$('#send-form').onsubmit=async event=>{
  event.preventDefault();const text=$('#message-input').value.trim();if(!text||!state.cid)return;
  const payload={conversation_id:state.cid,text,client_message_id:'web-'+Date.now()+'-'+Math.random().toString(36).slice(2),variant:state.selected===null?'CUSTOM':state.drafts[state.selected]?.variant,edited:state.selected!==null&&state.drafts[state.selected]?.text!==text};
  const m={id:payload.client_message_id,cid:state.cid,payload,text,sender_id:state.user.user_id,sender_name:state.user.display_name,sender_role:state.user.role,type:'text',pendingStatus:state.user.role==='teacher'?'质检发送中':'发送中'};
  state.pending.push(m);$('#message-input').value='';state.selected=null;renderMessages(true);sendPending(m);
};
async function sendPending(m){
  if(m.sending)return;m.sending=true;m.failed=false;m.pendingStatus=state.user.role==='teacher'?'质检发送中':'发送中';if(m.cid===state.cid)renderMessages(true);
  try{
    try{await post('/api/v1/messages',m.payload)}catch(e){
      if(e.status===409&&e.data.confirmation&&window.confirm((e.data.error||'请确认')+'\n'+(e.data.review?.suggestion||''))){m.payload.confirmation=e.data.confirmation;await post('/api/v1/messages',m.payload)}else throw e;
    }
    state.pending=state.pending.filter(x=>x!==m);if(m.cid===state.cid)await refreshMessages(true);
  }catch(e){m.failed=true;m.pendingStatus='发送未确认';toast(e.data?.review?.suggestion?e.message+'：'+e.data.review.suggestion:e.message)}
  finally{m.sending=false;if(m.cid===state.cid)renderMessages(true)}
}
$('#message-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('#send-form').requestSubmit()}});

function profileMarkup(p,compact=false){
  const a=p.activity||{};const tags=(p.manual_tags||[]).map(t=>`<span class="chip">${esc(t.tag)} <button class="subtle" data-remove-tag="${esc(t.tag)}" data-uid="${esc(p.user_id)}">×</button></span>`).join('');
  return `<div class="section-title"><div><span class="eyebrow">CUSTOMER PROFILE</span><h3>${esc(p.name)}</h3></div><span class="avatar">${esc(p.name?.slice(0,1)||'家')}</span></div>
  <div class="profile-section"><h4>阅读活跃度</h4><div class="chips"><span class="chip">${esc(a.level)}活跃</span><span class="chip">${esc(a.active_days)} 天阅读</span></div><p>${esc(a.window)} · 日均 ${esc(a.avg_minutes)} 分钟${a.missing?' · 部分数据缺失':''}</p></div>
  <div class="profile-section"><h4>意向度</h4><div class="chips"><span class="chip">${esc(p.intent?.level||'待识别')}</span></div><p>${p.intent?.signals?.length?'近期信号：'+esc(p.intent.signals.map(s=>s.type).join('、')):'暂无可确认的意向信号'}${p.intent?.pending_messages?' · 有消息待识别':''}</p></div>
  <div class="profile-section"><h4>最近行为概括</h4><p>${esc(p.summary||'尚未生成。可结合阅读行为与家长发言生成概括。')}</p>${p.summary_updated_at?`<p class="muted">更新于 ${esc(String(p.summary_updated_at).slice(0,16))}</p>`:''}<button class="subtle" data-summary="${esc(p.user_id)}">↻ 生成行为概括</button></div>
  <div class="profile-section"><h4>其他行为</h4><p>测字：${esc(p.tested||'暂无')}<br>会员链接点击：${esc(p.member_link_clicks??'暂无')}<br>报名：${esc(p.signup||'暂无')}</p></div>
  <div class="profile-section"><h4>人工标签</h4><div class="chips">${tags||'<span class="muted">暂无</span>'}</div><button class="subtle" data-add-tag="${esc(p.user_id)}">＋ 添加标签</button></div>`;
}
function bindProfileButtons(root){
  root.querySelectorAll('[data-summary]').forEach(b=>b.onclick=async()=>{b.disabled=true;b.textContent='正在生成…';try{await post('/api/v1/summary',{user_id:b.dataset.summary});await reloadProfile(b.dataset.summary)}catch(e){toast(e.message);b.disabled=false;b.textContent='↻ 生成行为概括'}});
  root.querySelectorAll('[data-add-tag]').forEach(b=>b.onclick=async()=>{const tag=window.prompt('输入标签');if(!tag)return;try{await post('/api/v1/tags',{user_id:b.dataset.addTag,tag});await reloadProfile(b.dataset.addTag)}catch(e){toast(e.message)}});
  root.querySelectorAll('[data-remove-tag]').forEach(b=>b.onclick=async()=>{try{await post('/api/v1/tags',{user_id:b.dataset.uid,tag:b.dataset.removeTag,remove:true});await reloadProfile(b.dataset.uid)}catch(e){toast(e.message)}});
}
async function reloadProfile(uid){const p=await api('/api/v1/profile/'+uid);if(state.profile?.user_id===uid){state.profile=p;renderSideProfile()}if(state.page==='profiles'||state.page==='workspace')loadDashboard()}
function renderSideProfile(){const root=$('#chat-profile');if(!state.profile){root.innerHTML='<div class="empty">选择家长消息后查看画像</div>';return}root.innerHTML=profileMarkup(state.profile,true);bindProfileButtons(root)}

async function loadDashboard(){
  if(dashboardRequest)return dashboardRequest;
  if(!state.dashboard){$('#dashboard-content').innerHTML='<div class="panel document">正在加载工作台数据…</div>';$('#profile-cards').innerHTML='<div class="panel document">正在加载用户画像…</div>'}
  else if($('#dashboard-status'))$('#dashboard-status').textContent='正在更新…';
  dashboardRequest=(async()=>{try{const data=await api('/api/v1/dashboard');state.dashboard=data;renderDashboard();renderProfiles();try{localStorage.setItem(dashboardCacheKey(),JSON.stringify({data,savedAt:Date.now()}))}catch{}$('#dashboard-status').textContent='已更新'}catch(e){if(state.dashboard){$('#dashboard-status').textContent='更新失败，当前显示缓存 · 点击刷新重试'}else{const message=`<div class="panel document">加载失败：${esc(e.message)} <button class="outline" data-dashboard-retry>重试</button></div>`;$('#dashboard-content').innerHTML=message;$('#profile-cards').innerHTML=message;document.querySelectorAll('[data-dashboard-retry]').forEach(b=>b.onclick=loadDashboard)}}finally{dashboardRequest=null}})();
  return dashboardRequest;
}
function renderDashboard(){
  const d=state.dashboard;if(!d)return;
  $('#dashboard-content').innerHTML=`<div class="welcome"><div><span class="eyebrow">HELLO, TEACHER</span><h2>今天也好好陪伴每一位家长</h2><p>关注真实互动，让每一次回复更从容。</p></div><button class="outline" id="go-chat">进入接待 →</button></div>
  <div class="metric-grid"><button class="metric panel" data-metric="today"><span>今日会话</span><strong>${d.today_conversations}</strong><small>今天发言的家长</small></button><button class="metric panel" data-metric="risk"><span>质检拦截</span><strong>${d.qc_count}</strong><small>需要关注的家长消息</small></button><button class="metric panel" data-metric="intent"><span>高意向用户</span><strong>${d.high_intent}</strong><small>近三日对话信号</small></button></div>
  <section class="panel follow-card"><div class="section-title"><div><span class="eyebrow">TODAY'S FOLLOW-UP</span><h3>今日跟进</h3><small id="dashboard-status" aria-live="polite"></small></div><button class="subtle" id="refresh-dashboard">刷新</button></div><div class="follow-list">${d.profiles.map(p=>`<div class="follow-row"><span class="avatar">${esc(p.name.slice(0,1))}</span><div><strong>${esc(p.name)}</strong><p>${esc(p.summary||`${p.activity.window}：${p.activity.active_days} 天，日均 ${p.activity.avg_minutes} 分钟`)} · 意向${esc(p.intent.level)}</p></div><button class="outline" data-open-user="${esc(p.user_id)}">查看对话</button></div>`).join('')}</div></section>`;
  $('#go-chat').onclick=()=>showPage('chat');$('#refresh-dashboard').onclick=loadDashboard;
  document.querySelectorAll('[data-open-user]').forEach(b=>b.onclick=()=>openUser(b.dataset.openUser));
  document.querySelectorAll('[data-metric]').forEach(b=>b.onclick=()=>showMetric(b.dataset.metric));
}
function showMetric(type){
  const d=state.dashboard;let title='',body='';
  if(type==='risk'){title='需要关注的家长消息';body=d.risks.map(r=>`<div class="follow-row"><span class="avatar">!</span><div><strong>${esc(r.details?.reason||'敏感消息')}</strong><p>${esc(r.time)}</p></div><button class="outline" data-risk-conv="${esc(r.conversation_id)}" data-risk-key="${esc(r.message_id)}">查看消息</button></div>`).join('')}
  else{title=type==='today'?'今日会话':'高意向用户';const list=type==='today'?d.profiles.filter(p=>(d.active_user_ids||[]).includes(p.user_id)):d.profiles.filter(p=>p.intent.level==='高');body=list.map(p=>`<div class="follow-row"><span class="avatar">${esc(p.name.slice(0,1))}</span><strong>${esc(p.name)}</strong><button class="outline" data-open-user="${esc(p.user_id)}">查看对话</button></div>`).join('')}
  $('#modal-content').innerHTML=`<h3>${title}</h3><div class="follow-list">${body||'<p class="muted">暂无记录</p>'}</div>`;$('#modal').classList.remove('hidden');
  $('#modal-content').querySelectorAll('[data-open-user]').forEach(b=>b.onclick=()=>{$('#modal').classList.add('hidden');openUser(b.dataset.openUser)});
  $('#modal-content').querySelectorAll('[data-risk-conv]').forEach(b=>b.onclick=async()=>{$('#modal').classList.add('hidden');await openConversation(b.dataset.riskConv);state.full=true;await refreshMessages(true);await selectTarget(b.dataset.riskKey,false)});
}
$('#close-modal').onclick=()=>$('#modal').classList.add('hidden');
function openUser(uid){const conv=state.conversations.find(c=>c.type==='direct'&&c.peer_id===uid);if(conv)openConversation(conv.id);else toast('暂无私聊');}
function renderProfiles(){const root=$('#profile-cards');root.innerHTML=(state.dashboard?.profiles||[]).map(p=>`<article class="panel profile-card" data-profile-card="${esc(p.user_id)}">${profileMarkup(p)}</article>`).join('');bindProfileButtons(root)}
setInterval(()=>{if(state.token&&state.page==='chat'&&!document.hidden)refreshMessages()},2500);
if(state.token)api('/api/v1/me').then(start).catch(()=>{sessionStorage.removeItem('opsie.token');state.token=null});
