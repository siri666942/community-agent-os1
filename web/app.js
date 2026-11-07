const assets = "./assets/";
const users = {
  xiaolin: {
    id:"xiaolin", name:"小林", avatar:assets+"xiaolin.png", time:"刚刚", tier:"S1 高价值推进",
    context:"高活跃度用户 · 高意向", status:"在线",
    summary:"近 7 天有 6 天活跃，连续查看专业课资料并完成 83% 试听课。今天主动询问优惠和下一步安排，转化窗口正在打开。",
    tags:["高活跃度用户","高意向","试听完成","价格关注"],
    manual:"已加两场直播课，沟通风格直接。希望在本周内确定班型。",
    behavior:[
      ["messages-square","会话与反馈","询问“报名后还有哪些规划”，表达希望尽快开始系统复习。"],
      ["book-open-check","产品使用","近 7 天打开资料 12 次；试听课观看 83%，测评完成 2 次。"],
      ["mouse-pointer-click","关键行为","今天 09:12 再次查看价格页，停留 4 分 26 秒。"]
    ],
    scores:[["活跃度","92"],["意向度","88"],["转化阶段","试听后"]],
    advice:"加紧推进下一步。趁用户表达明确规划需求，先询问备考时间与目标院校，再给出本期早鸟优惠，降低决策阻力。",
    script:"小林，你的试听完成度和资料使用频率都很高。你接下来打算把重点放在哪几科？如果计划 11 月开课，我可以按当前早鸟政策帮你核算对应班型，今天确认还能锁定本期优惠。",
    conversation:[
      {type:"day",text:"今天 09:08"},
      {type:"user",text:"老师，我昨天试听完了。这个全程班后面还有阶段性规划吗？"},
      {type:"ai",text:"有的。全程班会按基础、强化、冲刺三个阶段推进，并配套阶段测评与答疑。你更关注哪一科的复习安排？"},
      {type:"user",text:"我主要想把专业课提上来。现在报名是不是有什么优惠？"}
    ],
    replies:[
      {label:"推荐 · 推进转化",text:"我先按你的目标和时间做一个班型建议。现在报名有早鸟政策，具体能锁定的优惠以本期活动为准。你准备什么时候开始系统复习？",quality:"低风险 · 与课程政策一致"},
      {label:"稳妥 · 先问需求",text:"可以的。为了不推荐错班型，我先确认一下你的目标院校和每天可用复习时间，再把优惠方案一起发给你。",quality:"低风险 · 先补全画像"},
      {label:"简洁 · 促成行动",text:"现在有本期早鸟与团报优惠。你可以把目标院校和计划开课时间发我，我马上帮你核算对应班型。",quality:"注意 · 优惠以当期活动为准"}
    ],
    risk:false
  },
  zhouzhou: {
    id:"zhouzhou", name:"周周", avatar:assets+"zhouzhou.png", time:"8 分钟前", tier:"A2 意向培育",
    context:"价格敏感 · 观望中", status:"已读",
    summary:"近 3 天多次比较班型和价格，询问过资料、回放与师资。产品端仅试看 18%，尚未预约试听，当前更关注确定成本后再行动。",
    tags:["价格敏感","反复比价","未预约试听"],
    manual:"应届备考，预算有限。可优先介绍分期或团报，但不承诺额外折扣。",
    behavior:[
      ["messages-square","会话与反馈","关注总价、回放有效期和不同班型差异，尚未表达明确拒绝。"],
      ["play-circle","产品使用","课程详情页浏览 5 次，试看 18%，资料下载 1 次。"],
      ["timer-reset","跟进状态","距离上一次有效互动 8 分钟，适合在本次会话中推动预约。"]
    ],
    scores:[["活跃度","68"],["意向度","74"],["转化阶段","比价"]],
    advice:"先降低决策成本，再推进试听。明确解释班型差异和正式价格政策，避免承诺额外折扣；给出免费试听作为下一步。",
    script:"周周，如果现在主要比较预算，我可以按你的科目和学习基础帮你拆解不同班型的差异，避免多花费用。要不要先约一节免费试听？试听后再决定，也不会影响现有优惠资格。",
    conversation:[
      {type:"day",text:"今天 09:21"},
      {type:"user",text:"你们全程班到底多少钱？我看别人说价格不一样。"},
      {type:"ai",text:"课程价格会按科目、班型和服务内容分档，我需要按你的情况匹配正式价目，避免报错。"}
    ],
    replies:[
      {label:"推荐 · 价值拆解",text:"价格按科目、班型和服务内容分档。告诉我你的目标科目，我帮你按正式价目表拆解，比较哪档更适合你。",quality:"低风险 · 不承诺额外优惠"},
      {label:"转化 · 引导试听",text:"不同班型对应的服务和价格不同。可以先预约免费试听，体验课程后再确认班型，不会影响本期优惠资格。",quality:"低风险 · 试听邀约"},
      {label:"谨慎 · 口径说明",text:"我先发一份当前班型与服务对照表，最终价格以机构正式价目表为准。你更关心总价，还是单科价格？",quality:"注意 · 不口头锁定价格"}
    ],
    risk:false
  },
  jiajia: {
    id:"jiajia", name:"佳佳", avatar:assets+"jiajia.png", time:"22 分钟前", tier:"B3 待激活",
    context:"敏感问题 · 需人工审核", status:"待回复",
    summary:"入群 8 天，近 3 天只浏览过退款政策，未观看试听或下载资料。今天询问“是否可随时退款”，属于高风险敏感问题，已触发质检转人工。",
    tags:["待激活","退费关注","风险咨询"],
    manual:"昨日备注：家长可能对合同条款有顾虑，回复时不要催单。",
    behavior:[
      ["messages-square","会话与反馈","询问报名后能否随时退款，表达对合同约束的担忧。"],
      ["file-search","产品使用","查看退费政策 3 次，累计 6 分 12 秒；未观看课程内容。"],
      ["shield-alert","质检记录","命中风险动作“承诺可随时退款”，候选回复已拦截。"]
    ],
    scores:[["活跃度","31"],["意向度","46"],["转化阶段","风险澄清"]],
    advice:"优先处理顾虑，不推进促销。先发送正式退费规则并由人工解释，确认其顾虑是否来自退费、时间冲突或家人意见，再决定后续路径。",
    script:"佳佳，退费政策以你签署的课程服务协议为准。我先把正式规则发给你确认。考虑到这里涉及合同条款，我会请运营老师人工说明，确保信息准确，也先不给你额外的报名压力。",
    conversation:[
      {type:"day",text:"今天 09:36"},
      {type:"user",text:"我先问一下，要是报名以后发现不适合，能随时退款吗？"},
      {type:"ai",text:"质检检测到该问题涉及退款承诺，已暂停自动回复并转人工确认。"}
    ],
    replies:[
      {label:"合规 · 转人工",text:"退费政策以你签署的课程服务协议为准。我先把正式规则发给你确认，并同步请运营老师人工说明，确保信息准确。",quality:"已移除“随时退款”承诺"},
      {label:"澄清 · 识别顾虑",text:"我理解你在报名前想确认保障。我先发正式退费规则，同时想了解你更担心课程不适合，还是时间安排冲突？",quality:"注意 · 不承诺退费结果"},
      {label:"谨慎 · 仅发政策",text:"关于退费，应以正式课程服务协议中的条款为准。我可以把规则原文发给你，由运营老师再做说明。",quality:"低风险 · 避免解释争议"}
    ],
    risk:true
  }
};

const scenarios = [
  {name:"普通咨询",user:"zhouzhou",desc:"课程内容与回放规则",status:"已完成",progress:100,icon:"message-circle-question"},
  {name:"价格意向",user:"zhouzhou",desc:"报价、优惠与班型差异",status:"处理中",progress:68,icon:"badge-dollar-sign"},
  {name:"试听转化",user:"xiaolin",desc:"试听完成后的下一步",status:"待跟进",progress:52,icon:"calendar-check-2"},
  {name:"质检转人工",user:"jiajia",desc:"退费承诺风险拦截",status:"需人工",progress:36,icon:"shield-alert"},
  {name:"用户分层与跟进",user:"xiaolin",desc:"画像、标签与专属话术",status:"已生成",progress:88,icon:"chart-no-axes-combined"}
];

const sopSteps = [
  {name:"欢迎破冰",trigger:"新用户入群 / 首次私聊",time:"立即",talk:"识别届数、目标院校与专业",handoff:"要求人工、投诉"},
  {name:"需求识别",trigger:"用户回复个人情况",time:"10 分钟",talk:"已定院校推班型；未定给规划表",handoff:"深度择校咨询"},
  {name:"课程与价格",trigger:"价格 / 师资 / 优惠",time:"5 分钟",talk:"检索知识库报价，不编造",handoff:"退费、书面承诺"},
  {name:"试听邀约",trigger:"犹豫 / 比价 / 试听需求",time:"1 天",talk:"免费试听降低决策门槛",handoff:"无"},
  {name:"沉默激活",trigger:"3 天未互动 / 未转化",time:"3 天",talk:"回放引导 + 新班型介绍",handoff:"明确拒绝跟进"}
];

const pageTitles = {
  workspace:"运营工作台", chat:"客户对话", profile:"用户画像", sop:"SOP 流程", quality:"话术与质检", simulator:"客户端模拟"
};

let activeUserId = "xiaolin";
let activeScenario = "试听转化";
let selectedReply = 0;
let customMode = false;
let timeValue = 1;
let currentSopIndex = 3;

function icons(){ if(window.lucide) lucide.createIcons(); }

function showToast(text){
  const toast = document.querySelector("#toast");
  toast.querySelector("span").textContent = text;
  toast.classList.add("show");
  clearTimeout(window.toastTimer);
  window.toastTimer = setTimeout(()=>toast.classList.remove("show"),2600);
}

function goToPage(page){
  document.querySelectorAll(".nav-item").forEach(el=>el.classList.toggle("active",el.dataset.page===page));
  document.querySelectorAll(".page").forEach(el=>el.classList.toggle("active",el.id===`page-${page}`));
  document.querySelector("#page-title").textContent = pageTitles[page] || "运营工作台";
  window.scrollTo({top:0,behavior:"smooth"});
  icons();
}

function renderScenarios(){
  document.querySelector("#scenario-list").innerHTML = scenarios.map((s,i)=>{
    const u = users[s.user];
    return `<div class="scenario-row" data-scenario="${s.name}" data-user="${s.user}">
      <div class="scenario-icon"><i data-lucide="${s.icon}"></i></div>
      <div><strong>${s.name}</strong><small>${s.desc}</small></div>
      <div class="scenario-user"><img src="${u.avatar}" alt="${u.name}"><span>${u.name}</span></div>
      <div><small>${s.status}</small><div class="progress-mini"><span style="width:${s.progress}%"></span></div></div>
      <button class="icon-button" title="打开场景"><i data-lucide="arrow-up-right"></i></button>
    </div>`;
  }).join("");
  document.querySelectorAll(".scenario-row").forEach(row=>row.addEventListener("click",()=>{
    activeUserId=row.dataset.user;
    activeScenario=row.dataset.scenario;
    renderChat();
    goToPage("chat");
  }));

  document.querySelector("#sim-scenarios").innerHTML = scenarios.map(s=>`<button class="sim-scenario ${s.name===activeScenario?"active":""}" data-sim-scenario="${s.name}"><i data-lucide="${s.icon}"></i>${s.name}</button>`).join("");
  document.querySelectorAll("[data-sim-scenario]").forEach(btn=>btn.addEventListener("click",()=>{
    activeScenario=btn.dataset.simScenario;
    const match=scenarios.find(s=>s.name===activeScenario);
    if(match) activeUserId=match.user;
    renderSimulator();
  }));
}

function renderFollowList(){
  document.querySelector("#dashboard-follow-list").innerHTML = Object.values(users).map(u=>`
    <button class="follow-card" data-follow-user="${u.id}">
      <img src="${u.avatar}" alt="${u.name}">
      <div><strong>${u.name} · ${u.tier}</strong><span>${u.advice.slice(0,34)}...</span></div>
      <span class="tag ${u.id==="jiajia"?"amber":u.id==="zhouzhou"?"blue":""}">${u.tags[0]}</span>
    </button>`).join("");
  document.querySelectorAll("[data-follow-user]").forEach(btn=>btn.addEventListener("click",()=>{
    activeUserId=btn.dataset.followUser;
    renderChat();
    goToPage("chat");
  }));
}

function renderCustomerCards(){
  document.querySelector("#customer-cards").innerHTML = Object.values(users).map(u=>`
    <button class="customer-card ${u.id===activeUserId?"active":""}" data-customer="${u.id}">
      <img src="${u.avatar}" alt="${u.name}">
      <div><strong>${u.name}</strong><span>${u.conversation[u.conversation.length-1].text}</span></div>
      <time>${u.time}</time>
    </button>`).join("");
  document.querySelectorAll("[data-customer]").forEach(btn=>btn.addEventListener("click",()=>{
    activeUserId=btn.dataset.customer;
    selectedReply=0;
    customMode=false;
    renderChat();
  }));
}

function renderMessages(){
  const u=users[activeUserId];
  const stage=document.querySelector("#message-stage");
  stage.innerHTML=u.conversation.map(m=>{
    if(m.type==="day") return `<div class="day-divider">${m.text}</div>`;
    const cls=m.type==="user"?"user":m.type==="system"?"system":"";
    const img=m.type==="user"?u.avatar:assets+"brand-mark.png";
    return `<div class="message ${cls}"><img class="bubble-avatar" src="${img}" alt=""><div><div class="meta">${m.type==="user"?u.name:"服务运营智能体"}</div><div class="bubble">${m.text}</div></div></div>`;
  }).join("");
  stage.scrollTop=stage.scrollHeight;
}

function renderReplyOptions(){
  const u=users[activeUserId];
  document.querySelector("#reply-options").innerHTML=u.replies.map((r,i)=>`
    <button class="reply-option ${selectedReply===i&&!customMode?"selected":""}" data-reply-index="${i}">
      <b>${r.label}</b>${r.text}
      <span class="quality-line"><i data-lucide="shield-check"></i>${r.quality}</span>
    </button>`).join("");
  document.querySelectorAll("[data-reply-index]").forEach(btn=>btn.addEventListener("click",()=>{
    selectedReply=Number(btn.dataset.replyIndex);
    customMode=false;
    renderReplyOptions();
  }));
  const alert=document.querySelector("#risk-alert");
  alert.classList.toggle("hidden",!u.risk);
  if(u.risk) document.querySelector("#risk-text").textContent="识别到“随时退款”等承诺性表达，候选回复必须由运营老师人工审核后发送。";
  const send=document.querySelector("#send-reply");
  send.innerHTML=u.risk?'<i data-lucide="user-check"></i>确认合规并发送':'<i data-lucide="send"></i>审核并发送';
  icons();
}

function renderChatProfile(){
  const u=users[activeUserId];
  document.querySelector("#chat-profile").innerHTML=`
    <div class="profile-identity"><img src="${u.avatar}" alt="${u.name}"><strong>${u.name}</strong><span>${u.context}</span></div>
    <div class="profile-score">${u.scores.map(s=>`<div class="score-cell"><strong>${s[1]}</strong><span>${s[0]}</span></div>`).join("")}</div>
    <div class="mini-section"><strong>最近行为概括</strong><p>${u.summary}</p></div>
    <div class="mini-section"><strong>AI 标签</strong><div>${u.tags.map((t,i)=>`<span class="tag ${i%2?"blue":""}">${t}</span>`).join("")}</div></div>
    <div class="mini-section"><strong>人工备注</strong><p>${u.manual}</p></div>
    <div class="mini-section"><strong>下一建议</strong><p>${u.advice}</p></div>`;
}

function renderChat(){
  const u=users[activeUserId];
  document.querySelector("#active-avatar").src=u.avatar;
  document.querySelector("#active-avatar").alt=u.name;
  document.querySelector("#active-name").textContent=u.name;
  document.querySelector("#active-context").textContent=u.context;
  renderCustomerCards();
  renderMessages();
  renderReplyOptions();
  renderChatProfile();
  renderSimulator();
  icons();
}

function renderProfileList(){
  document.querySelector("#profile-user-list").innerHTML=Object.values(users).map(u=>`
    <button class="profile-user-card ${u.id===activeUserId?"active":""}" data-profile-user="${u.id}">
      <img src="${u.avatar}" alt="${u.name}">
      <div><strong>${u.name} · ${u.tier}</strong><span>${u.tags.slice(0,3).join(" · ")}</span></div>
    </button>`).join("");
  document.querySelectorAll("[data-profile-user]").forEach(btn=>btn.addEventListener("click",()=>{
    activeUserId=btn.dataset.profileUser;
    renderProfileList();
    renderProfileDetail();
    renderSimulator();
    icons();
  }));
}

function renderProfileDetail(){
  const u=users[activeUserId];
  document.querySelector("#profile-detail").innerHTML=`
    <div class="profile-hero">
      <img src="${u.avatar}" alt="${u.name}">
      <div><h2>${u.name}</h2><p>${u.context} · ${u.status}</p><div>${u.tags.slice(0,3).map((t,i)=>`<span class="tag ${i===1?"blue":i===2?"amber":""}">${t}</span>`).join("")}</div></div>
      <div class="layer-badge"><span>建议分层</span><strong>${u.tier}</strong></div>
    </div>
    <div class="profile-columns">
      <section class="profile-block">
        <h3>最近行为概括</h3>
        <div class="behavior-summary">${u.summary}</div>
        <div style="margin-top:10px">${u.behavior.map(b=>`<div class="data-source"><i data-lucide="${b[0]}"></i><div><strong>${b[1]}</strong><span>${b[2]}</span></div></div>`).join("")}</div>
      </section>
      <div>
        <section class="profile-block">
          <h3>标签与人工备注</h3>
          <div class="tag-editor">
            ${u.tags.map((t,i)=>`<span class="tag-chip ${i===3?"manual":""}">${i===3?'<i data-lucide="user-round-pen"></i>':""}${t}<button title="删除标签"><i data-lucide="x"></i></button></span>`).join("")}
            <button class="add-tag">+ 人工备注标签</button>
          </div>
          <div class="data-source" style="margin-top:12px"><i data-lucide="notebook-pen"></i><div><strong>运营老师备注</strong><span>${u.manual}</span></div></div>
        </section>
        <section class="profile-block" style="margin-top:12px">
          <h3>转化阶段与数据</h3>
          ${u.scores.map(s=>`<div class="data-source"><i data-lucide="chart-spline"></i><div><strong>${s[0]} · ${s[1]}</strong><span>${s[0]==="转化阶段"?"基于当前 SOP 状态机":"基于近 7 天行为动态计算"}</span></div></div>`).join("")}
        </section>
      </div>
    </div>
    <div class="recommendation">
      <i data-lucide="sparkles"></i>
      <div><strong>分层建议与专属话术</strong><span>${u.advice}</span><span style="background:#fff;padding:9px;border-radius:6px;margin-top:8px;color:#4e4358">“${u.script}”</span></div>
      <button class="button primary" id="copy-script"><i data-lucide="copy"></i>使用话术</button>
    </div>`;
  document.querySelector("#copy-script").addEventListener("click",()=>{
    document.querySelector("#custom-reply-input").value=u.script;
    customMode=true;
    showToast("专属话术已带入自定义回复");
    goToPage("chat");
    renderReplyOptions();
  });
  icons();
}

function renderSop(){
  document.querySelector("#sop-flow").innerHTML=sopSteps.map((s,i)=>`
    <article class="sop-card">
      <div class="sop-num">0${i+1}</div>
      <h3>${s.name}</h3>
      <p>${s.talk}</p>
      <div class="sop-meta">
        <span><i data-lucide="zap"></i>${s.trigger}</span>
        <span><i data-lucide="timer"></i>${s.time}</span>
        <span><i data-lucide="user-round-cog"></i>${s.handoff}</span>
      </div>
    </article>`).join("");
  document.querySelector("#sop-step-select").innerHTML=sopSteps.map((s,i)=>`<option value="${i}">${s.name}</option>`).join("");
}

function renderSimulator(){
  const u=users[activeUserId];
  document.querySelector("#sim-user-buttons").innerHTML=Object.values(users).map(x=>`<button class="sim-user ${x.id===activeUserId?"active":""}" data-sim-user="${x.id}"><img src="${x.avatar}" alt="${x.name}" title="${x.name}"></button>`).join("");
  document.querySelectorAll("[data-sim-user]").forEach(btn=>btn.addEventListener("click",()=>{
    activeUserId=btn.dataset.simUser;
    renderSimulator();
  }));
  const visible=u.conversation.filter(m=>m.type!=="day").slice(-8);
  document.querySelector("#phone-messages").innerHTML=visible.map(m=>`
    <div class="phone-message ${m.type==="user"?"mine":""}"><div class="bubble">${m.text}</div><time>${m.type==="user"?"09:42":"09:43"}</time></div>`).join("");
  document.querySelectorAll("[data-sim-scenario]").forEach(btn=>btn.classList.toggle("active",btn.dataset.simScenario===activeScenario));
  icons();
}

function openModal(id){ document.querySelector(id).classList.remove("hidden"); icons(); }
function closeModals(){ document.querySelectorAll(".modal-layer").forEach(m=>m.classList.add("hidden")); }

document.addEventListener("DOMContentLoaded",()=>{
  renderScenarios();
  renderFollowList();
  renderSop();
  renderChat();
  renderProfileList();
  renderProfileDetail();
  renderSimulator();
  icons();

  document.querySelector("#mobile-menu").addEventListener("click",()=>document.querySelector(".sidebar").classList.toggle("open"));
  document.querySelectorAll(".nav-item").forEach(btn=>btn.addEventListener("click",()=>{goToPage(btn.dataset.page);document.querySelector(".sidebar").classList.remove("open");}));
  document.querySelectorAll("[data-page-jump]").forEach(btn=>btn.addEventListener("click",()=>goToPage(btn.dataset.pageJump)));
  document.querySelectorAll(".jump-chat").forEach(btn=>btn.addEventListener("click",()=>goToPage("chat")));

  document.querySelector("#open-import").addEventListener("click",()=>openModal("#import-modal"));
  document.querySelectorAll(".close-modal").forEach(btn=>btn.addEventListener("click",closeModals));
  document.querySelectorAll(".modal-layer").forEach(layer=>layer.addEventListener("click",e=>{if(e.target===layer) closeModals();}));
  document.querySelector("#confirm-import").addEventListener("click",()=>{
    closeModals();
    showToast("公司 SOP 已解析并上线");
    goToPage("sop");
  });

  document.querySelector("#simulate-user").addEventListener("click",()=>{
    const u=users[activeUserId];
    const prompts={
      xiaolin:"那如果我这周确定，后面报名和开课怎么安排？",
      zhouzhou:"我预算有限，你们到底有没有额外优惠？",
      jiajia:"那要是老师不适合我，能随时退款吗？"
    };
    u.conversation.push({type:"user",text:prompts[activeUserId]});
    if(activeUserId==="jiajia"){
      activeScenario="质检转人工";
      u.risk=true;
    }
    renderMessages();
    renderReplyOptions();
    renderSimulator();
    showToast("已模拟用户提问，AI 正在生成 3 个候选");
  });

  document.querySelector("#custom-reply-input").addEventListener("input",e=>{
    customMode=e.target.value.trim().length>0;
    renderReplyOptions();
  });

  document.querySelector("#send-reply").addEventListener("click",()=>{
    const u=users[activeUserId];
    const input=document.querySelector("#custom-reply-input");
    const text=customMode&&input.value.trim()?input.value.trim():u.replies[selectedReply].text;
    u.conversation.push({type:"ai",text});
    input.value="";
    customMode=false;
    renderMessages();
    renderSimulator();
    showToast(u.risk?"人工审核通过，已回复并写入场景记忆":"回复已发送，本次偏好已写入场景记忆");
  });

  document.querySelector("#refresh-profile").addEventListener("click",()=>{
    renderProfileDetail();
    showToast("画像已融合最新会话与产品行为");
  });

  const openSop=()=>openModal("#sop-modal");
  document.querySelector("#adjust-sop").addEventListener("click",openSop);
  document.querySelector("#adjust-sop-inline").addEventListener("click",openSop);
  document.querySelector("#time-minus").addEventListener("click",()=>{timeValue=Math.max(.5,timeValue-.5);document.querySelector("#time-value").textContent=`${timeValue} 天`;});
  document.querySelector("#time-plus").addEventListener("click",()=>{timeValue=Math.min(7,timeValue+.5);document.querySelector("#time-value").textContent=`${timeValue} 天`;});
  document.querySelector("#sop-step-select").addEventListener("change",e=>{
    currentSopIndex=Number(e.target.value);
    const raw=sopSteps[currentSopIndex].time;
    timeValue=raw==="立即"?0.5:Number(raw.replace(" 天",""))||1;
    document.querySelector("#time-value").textContent=`${timeValue} 天`;
  });
  document.querySelector("#save-sop-change").addEventListener("click",()=>{
    closeModals();
    document.querySelector("#retention-step").textContent=sopSteps[currentSopIndex].name;
    document.querySelector("#retention-time").textContent=`${timeValue} 天`;
    openModal("#retention-modal");
  });
  document.querySelectorAll("[data-retention]").forEach(btn=>btn.addEventListener("click",()=>{
    const keep=btn.dataset.retention==="keep";
    if(keep){
      sopSteps[currentSopIndex].time=`${timeValue} 天`;
      renderSop();
      document.querySelector("#change-history").innerHTML=`<span><i data-lucide="history"></i>${sopSteps[currentSopIndex].name} 已由 1 天调整为 ${timeValue} 天，并保存为公司 SOP 默认规则</span>`;
    }
    closeModals();
    showToast(keep?"修改已保存，供下次 SOP 流程使用":"修改仅用于本次场景，不改变默认 SOP");
    icons();
  }));

  document.querySelector("#upload-script").addEventListener("click",()=>{
    openModal("#import-modal");
    document.querySelector("#import-modal h3").textContent="上传公司话术库";
    document.querySelector("#import-modal .upload-zone strong").textContent="拖入 Excel / Word / PDF 话术库";
    document.querySelector("#import-modal .parse-preview strong").textContent="识别到 12 条标准口径、4 条禁止词与风险动作";
    document.querySelector("#confirm-import").innerHTML='<i data-lucide="check"></i>确认启用';
    icons();
  });

  document.querySelector("#reset-simulator").addEventListener("click",()=>{
    activeUserId="xiaolin";
    activeScenario="试听转化";
    renderSimulator();
    showToast("客户端模拟已重置");
  });
});

