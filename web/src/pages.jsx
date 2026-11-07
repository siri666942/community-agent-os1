import { useState } from 'react';
import {
  ArrowRight, ArrowUpRight, Bot, BookOpen, CalendarDays, ChartNoAxesCombined,
  Check, CheckCircle2, ChevronRight, ClipboardList, FileText, HeartHandshake, Send,
  Layers, MessageCircle, RefreshCw, ShieldCheck, Sparkles, UsersRound, WandSparkles
} from 'lucide-react';
import { Block, Empty, Metric, Panel, PageHeading, StatusBadge, Interrupted } from './ui';
import { approvalItems, packageMaterial, statusLabel } from './lib';

const count = (n, ready) => ready ? String(n).padStart(2, '0') : '—';

export function Home({ ctx }) {
  const { go, tickets, packages, approvals, workflow, connected, connectionError, refresh } = ctx;
  return <div className="home-page">
    <header className="home-nav container">
      <button type="button" className="brand-logo" onClick={() => go('home')} aria-label="回到首页">
        <span className="brand-symbol"><Layers size={21}/></span>
        <span><strong>伴学管家 <i>OPC</i></strong><small>ONE-PERSON COMPANY</small></span>
      </button>
      <nav aria-label="首页导航" className="home-links">
        <a href="#features">产品能力</a><a href="#workflow">工作方式</a><a href="#team">AI 团队</a>
      </nav>
      <button className="button primary home-nav-button" onClick={() => go('dashboard')}>进入工作台 <ArrowUpRight size={15}/></button>
    </header>
    {connectionError && <div className="home-offline container" role="alert"><span>{connectionError} · 部分业务数据暂不可用，请检查后端连接。</span><button onClick={refresh}>重试连接</button></div>}
    <main>
      <section className="home-hero container">
        <div className="hero-copy">
          <div className="eyebrow-pill"><Sparkles size={14}/> AI OPERATIONS · EDUCATION SERVICE</div>
          <h1>一个人，<br/><em>一支团队。</em></h1>
          <p className="hero-en">One person. A whole team.</p>
          <p className="hero-description">让数据增长与服务运营 Agent 协同工作。从客户消息、内容审核到业务复盘，交给 AI 处理琐事，把关键决定留给你。</p>
          <div className="hero-actions">
            <button className="button primary" onClick={() => go('dashboard')}>探索工作空间 <ArrowRight size={17}/></button>
            <a className="button outline" href="#features">了解产品 <ChevronRight size={16}/></a>
          </div>
          <div className="hero-highlights"><span><CheckCircle2 size={16}/> 两个业务 Agent</span><span><ShieldCheck size={16}/> 人工审核闸门</span><span><Layers size={16}/> 本地工作空间</span></div>
        </div>
        <div className="hero-showcase" aria-label="真实工作空间功能预览">
          <div className="showcase-backdrop" aria-hidden="true"></div>
          <div className="showcase-window">
            <div className="preview-sidebar">
              <div className="preview-brand"><span className="preview-mark">✳</span><span>伴学管家 OPC</span></div>
              <div className="preview-menu"><span className="current">▦　总览指挥舱</span><span>◎　Agent 工作台</span><span>↗　增长协作</span><span>▤　运营中心</span><span>◇　风控与审批</span><span>▥　经营分析</span></div>
              <div className="preview-bottom">LOCAL-FIRST</div>
            </div>
            <div className="preview-content">
              <div className="preview-top"><span>WORKSPACE / OVERVIEW</span><span className="preview-circle">OPC</span></div>
              <h2>下午好，今天的团队进度如何？</h2>
              <p>一人指挥，AI 分工协作，关键环节由你审批。</p>
              <div className="preview-metrics">
                <div><span>累计工单</span><strong>{count(tickets.length, connected)}</strong><small>服务运营</small></div>
                <div><span>运营包</span><strong>{count(packages.length, connected)}</strong><small>日度内容</small></div>
                <div><span>待人工处理</span><strong>{count(approvals.length, connected)}</strong><small>审批队列</small></div>
              </div>
              <div className="preview-board">
                <div className="preview-flow">
                  <div className="preview-board-label">TEAM WORKFLOW <span>业务流程示意</span></div>
                  <div className="preview-flow-steps"><div><i>01</i><b>理解数据</b><small>数据增长</small></div><ChevronRight size={17}/><div><i>02</i><b>准备内容</b><small>服务运营</small></div><ChevronRight size={17}/><div><i>03</i><b>人工审批</b><small>关键闸门</small></div></div>
                  <div className="preview-flow-footer"><CheckCircle2 size={14}/> 可审查的业务协作链</div>
                </div>
                <div className="preview-mini"><div className="preview-board-label">TEAM ROSTER</div><div><span className="preview-avatar">A</span><span>服务运营 Agent<small>客服 · 内容 · 审核</small></span></div><div><span className="preview-avatar alternate">B</span><span>数据增长 Agent<small>分层 · 规划 · 分析</small></span></div></div>
              </div>
            </div>
          </div>
          <div className="showcase-foot">伴学管家 OPC <span>·</span> 界面预览使用当前本地记录，未连接时显示占位符</div>
        </div>
      </section>
      <div className="home-trust container"><span>BUILT FOR MEANINGFUL WORK</span><div><span>教育服务</span><span>私域运营</span><span>内容生产</span><span>业务分析</span><span>人工审批</span></div></div>
      <section className="home-features container" id="features">
        <div className="section-heading"><div className="section-kicker">01 / THE ADVANTAGE</div><h2>让智能，<em>更简单。</em></h2><p>不是堆叠功能，而是让小团队真正拥有一套可靠的工作流程。</p></div>
        <div className="feature-grid">
          <article><div className="feature-icon"><UsersRound size={22}/></div><h3>一人经营，多人协作</h3><p>由业务 Agent 执行专业任务，一人也能组织清晰的服务与运营流程。</p></article>
          <article><div className="feature-icon"><WandSparkles size={22}/></div><h3>从输入到交付</h3><p>处理消息、生成内容、进行审核，贯穿运营工作的实际环节。</p></article>
          <article><div className="feature-icon"><ShieldCheck size={22}/></div><h3>把决定留给人</h3><p>对高风险事项和正式交付设置明确闸门，记录每一次审核与决定。</p></article>
        </div>
      </section>
      <section className="home-workflow-band" id="workflow"><div className="container workflow-layout">
        <div className="section-heading"><div className="section-kicker">02 / BEYOND CONVERSATION</div><h2>真正运行的，<br/><em>不只是对话。</em></h2><p>让 AI 从“回答问题”进入“处理任务”，保留过程记录和明确的人工决策权。</p><button className="text-link" onClick={() => go('workspace')}>体验一次协作 <ArrowUpRight size={16}/></button></div>
        <div className="workflow-steps">{[[FileText,'接收需求','消息与知识'],[Bot,'协作执行','生成与分析'],[ShieldCheck,'审核把关','人工审批'],[ChartNoAxesCombined,'留下结果','可追溯记录']].map(([Icon,title,subtitle],index)=><div className="step-wrap" key={title}><div className="step-card"><span className="step-index">0{index+1}</span><Icon size={27}/><h3>{title}</h3><p>{subtitle}</p></div>{index!==3&&<ArrowRight className="step-arrow" size={18}/>}</div>)}</div>
      </div></section>
      <section className="home-team container" id="team"><div className="section-heading"><div className="section-kicker">03 / MEET YOUR TEAM</div><h2>少一些角色堆砌，<br/><em>多一些真正协作。</em></h2><p>两个业务 Agent，搭配独立审核步骤与人类经营者，组成可控的微型业务团队。</p></div>
        <div className="team-grid"><article><span className="team-figure"><HeartHandshake size={26}/></span><small>AGENT 01 / CARE</small><h3>服务运营 Agent</h3><p>客服应答、运营内容、合规审核、工单归档。</p></article><article><span className="team-figure"><ChartNoAxesCombined size={26}/></span><small>AGENT 02 / GROWTH</small><h3>数据增长 Agent</h3><p>客户分层、跟进计划、数据分析和反馈。</p></article><article><span className="team-figure"><Check size={26}/></span><small>HUMAN IN THE LOOP</small><h3>人类经营者</h3><p>确认关键节点、批准内容、承担最终决策。</p></article></div>
      </section>
      <section className="home-cta"><span>ONE PERSON. A WHOLE TEAM.</span><h2>把时间，留给重要的事。</h2><button className="button primary" onClick={() => go('dashboard')}>进入伴学管家 <ArrowUpRight size={17}/></button></section>
    </main>
    <footer className="home-footer container"><span>伴学管家 OPC · JUNCTION CHINA 2026</span><span>本地演示：不连接真实发送渠道，不执行真实退款</span></footer>
  </div>;
}

export function Dashboard({ ctx }) {
  const { tickets, packages, approvals, go, connected, refresh } = ctx;
  const total = tickets.length;
  const riskCounts = ['L1','L2','L3'].map(level => tickets.filter(ticket => ticket.risk_level === level).length);
  const unspecified = Math.max(0, total - riskCounts.reduce((sum, n) => sum + n, 0));
  const categories = [
    { name: 'L1 常规', value: riskCounts[0], color: '#246bff' },
    { name: 'L2 关注', value: riskCounts[1], color: '#959aa5' },
    { name: 'L3 高风险', value: riskCounts[2], color: '#ffac32' },
    { name: '未分级', value: unspecified, color: '#e9ebef' }
  ];
  let angle = 0;
  const stops = categories.map(({ value, color }) => {
    const start = angle;
    angle += total ? value / total * 100 : 0;
    return color + ' ' + start.toFixed(2) + '% ' + angle.toFixed(2) + '%';
  });
  const circle = total ? 'conic-gradient(' + stops.join(',') + ')' : '#f0f2f5';
  const today = new Date();
  const days = Array.from({ length: 7 }, (_, index) => {
    const date = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 6 + index);
    const rows = tickets.filter(ticket => {
      const t = new Date(ticket.time || ticket.created_at || '');
      return !Number.isNaN(t.getTime()) && t.toDateString() === date.toDateString();
    });
    return {
      key: date.toDateString(),
      label: (date.getMonth() + 1) + '/' + date.getDate(),
      all: rows.length,
      high: rows.filter(ticket => ticket.risk_level === 'L3').length
    };
  });
  const highest = Math.max(1, ...days.map(day => day.all));
  const validDated = days.reduce((sum, day) => sum + day.all, 0);
  const recent = tickets.slice(0, 6); // API already sorts tickets by time descending.

  return <div className="dashboard-page">
    <div className="dashboard-heading">
      <div><span className="overline">PRIVATE DOMAIN / OVERVIEW</span><h1>运营总览</h1><p>查看客户咨询、跟进任务和需要人工处理的事项。</p></div>
      <button className="period-button" type="button" onClick={refresh}><CalendarDays size={16}/> 本地实时记录 <RefreshCw size={14}/></button>
    </div>
    <div className="info-note">本地演示环境：系统不发送消息，也不执行退款。模拟客户和模拟回执均会标注。</div>
    <div className="workspace-grid" style={{margin:'20px 0'}}>
      <Panel title="快捷入口" description="从日常运营常用页面开始。">
        <div className="action-row"><button className="button primary" onClick={()=>go('workspace')}>处理客户会话</button><button className="button outline" onClick={()=>go('customers')}>查看客户画像</button><button className="button outline" onClick={()=>go('operations')}>生成 SOP 内容</button><button className="button outline" onClick={()=>go('growth')}>查看跟进线索</button></div>
        <p className="muted">所有操作都会标明本地记录、模拟内容与人工审批状态。</p>
      </Panel>
      <Panel title="需要你处理" description="当前本地待审批和人工复核事项"><p>{connected ? approvals.length + ' 项待处理' : '数据暂不可用'}</p><button className="button outline" onClick={()=>go('risk')}>查看审批中心</button><p className="muted">进行中的任务：{(ctx.workflow?.runs||[]).filter(r=>r.status==='RUNNING').length} 项（当前本地记录）</p></Panel>
    </div>
    <div className="dashboard-layout">
      <div className="dashboard-primary">
        <div className="dashboard-kpis">
          <article className="kpi-dark">
            <div className="kpi-top"><span className="orange-indicator"/> TEAM UPDATE <span className="kpi-icon">↗</span></div>
            <span className="kpi-date">当前业务队列</span>
            <h2>{approvals.length ? <>有 <em>{approvals.length}</em> 项事项<br/>等待人工处理</> : <>客户沟通与运营<br/>记录一目了然</>}</h2>
            <button type="button" onClick={() => go(approvals.length ? 'risk' : 'workspace')}>{approvals.length ? '查看待处理事项' : '进入客户会话'} <ArrowRight size={15}/></button>
            <div className="dark-card-wave" aria-hidden="true"/>
          </article>
          <article className="kpi-card">
            <div className="kpi-label"><span>累计客户会话</span><ClipboardList size={18}/></div>
            <div className="kpi-number">{connected ? total : '—'}</div>
            <div className="kpi-foot"><span className="tiny-blue"><ArrowUpRight size={14}/> SERVICE</span>来自本地工单记录</div>
          </article>
          <article className="kpi-card">
            <div className="kpi-label"><span>运营内容包</span><BookOpen size={18}/></div>
            <div className="kpi-number">{connected ? packages.length : '—'}</div>
            <div className="kpi-foot"><span className="tiny-orange"><Layers size={13}/> SOP</span>来自本地生成记录</div>
          </article>
        </div>
        <div className="dashboard-detail-grid">
          <section className="dash-panel recent-panel">
            <div className="dash-panel-head"><div><h2>最近工单</h2><p>Recent activity</p></div><button aria-label="查看所有工单" type="button" onClick={() => go('workspace')}><ArrowUpRight size={18}/></button></div>
            {recent.length ? <div className="recent-list">{recent.map((ticket, index) =>
              <button type="button" className="recent-entry" key={ticket.id || index} onClick={() => ctx.openTicket(ticket.id)} title="查看完整工单详情">
                <span className={'entry-mark '+ (ticket.risk_level === 'L3' ? 'high' : 'normal')}><FileText size={17}/></span>
                <div className="entry-text"><strong>{ticket.message || ticket.id || '工单记录'}</strong><small>{ticket.time || ticket.id || '本地已归档'}</small></div>
                <span className={'entry-badge '+ (ticket.risk_level === 'L3' ? 'high' : '')}>{ticket.risk_level || '未分级'}</span>
            </button>)}</div> : <div className="dashboard-empty"><FileText size={25}/><strong>还没有会话记录</strong><p>提交第一条家长咨询后会显示在这里。</p><button type="button" onClick={() => go('workspace')}>开始处理 <ArrowRight size={14}/></button></div>}
          </section>
          <div className="dashboard-charts">
            <section className="dash-panel trends-panel">
              <div className="dash-panel-head"><div><h2>工单趋势</h2><p>最近七天 · 按本地时间统计</p></div><span className="chart-legend"><i/>全部 <i className="orange"/>L3 风险</span></div>
              <div className="trend-total"><strong>{validDated}</strong><span>近七天有时间戳的工单</span></div>
              <div className="trend-chart" role="img" aria-label={days.map(day => day.label+'：'+day.all+' 条工单，L3 风险 '+day.high+' 条').join('；')}>
                {days.map(day => <div className="trend-day" key={day.key}>
                  <div className="trend-bars"><div className="trend-bar blue" style={{height: (day.all ? Math.max(7, day.all / highest * 100) : 0)+'%'}}/><div className="trend-bar orange" style={{height: (day.high ? Math.max(7, day.high / highest * 100) : 0)+'%'}}/></div>
                  <span>{day.label}</span>
                </div>)}
              </div>
            </section>
            <section className="dash-panel analytics-preview">
              <div className="dash-panel-head"><div><h2>业务概览</h2><p>本地记录统计</p></div><button type="button" aria-label="打开经营分析" onClick={() => go('analytics')}><ArrowUpRight size={18}/></button></div>
              <div className="mini-bar-list">
                {[['客服工单',total,'blue'],['运营包',packages.length,'soft-blue'],['待人工处理',approvals.length,'orange']].map(([name,value,color]) => {
                  const max = Math.max(1, total, packages.length, approvals.length);
                  return <div className="mini-bar-row" key={name}><span>{name} <strong>{value}</strong></span><div className="mini-bar-track"><i className={color} style={{width: (value/max*100)+'%'}}/></div></div>;
                })}
              </div>
            </section>
          </div>
        </div>
      </div>
      <aside className="dashboard-rail">
        <section className="dash-panel performance-panel">
          <div className="dash-panel-head centered"><h2>工单风险分布</h2><p>Risk distribution</p></div>
          <div className="donut-wrap">
            <div className="donut" role="img" aria-label={categories.map(item => item.name+item.value+'条').join('，')} style={{background: circle}}>
              <div className="donut-center"><span>工单总数</span><strong>{connected ? total : '—'}</strong><small>LOCAL RECORDS</small></div>
            </div>
          </div>
          <div className="donut-legend">{categories.filter(item => item.value || item.name !== '未分级').map(item =>
            <div key={item.name}><i style={{background: item.color}}/><span>{item.name}</span><strong>{item.value}</strong></div>)}</div>
          <p className="donut-caption">统计基于已归档工单的实际风险等级，未分级记录单独计算。</p>
          <button className="button outline full" type="button" onClick={() => go('analytics')}>查看完整分析 <ArrowRight size={15}/></button>
        </section>
        <section className="rail-promo">
          <span className="rail-star">✳</span>
          <span className="overline">TWO AGENTS. ONE TEAM.</span>
          <h2>跟进有记录，<br/>沟通有依据。</h2>
          <p>查看客户状态与跟进建议，关键事项由人工确认。</p>
          <div className="rail-curve" aria-hidden="true"/>
          <button type="button" className="button blue full" onClick={() => go('growth')}>查看 Agent 协作 <ArrowUpRight size={16}/></button>
        </section>
      </aside>
    </div>
  </div>;
}

export function Workspace({ ctx }) {
  const [message,setMessage] = useState(ctx.demo ? '这个课程适合几岁的孩子？' : '');
  const [customer,setCustomer] = useState('');
  const ticket = ctx.tickets.find(item => item.id === ctx.selectedTicketId) || ctx.ticket || ctx.tickets[0];
  const customers = ctx.workflow?.analysis?.customers || [];
  const submit = e => { e.preventDefault(); if(message.trim())ctx.run('/api/service',{message:message.trim(),customer_id:customer,demo:ctx.demo && !customer},r=>{ const created=r.ticket||r; ctx.setTicket(created); ctx.setSelectedTicketId(created.id||null); }); };
  return <><PageHeading kicker="CUSTOMER CONVERSATIONS" title="客户会话" description="集中处理家长咨询，查看回复草稿与审核结果。系统不会自动发送消息。"/>
    <div className="form-grid"><Panel title="发起客服任务" description="输入真实问题，启动业务工作流"><form className="field-stack" onSubmit={submit}>
      <label htmlFor="customer">客户记录</label><select id="customer" value={customer} onChange={e=>setCustomer(e.target.value)}><option value="">新建入站客户（默认无触达同意）</option>{customers.map(c=><option key={c.customer_id} value={c.customer_id}>{c.customer_id} · {c.source} · {c.consent?'已记录同意':'未记录同意'}</option>)}</select>
      {ctx.demo && !customer && <p className="info-note">演示案例：此消息创建模拟入站客户，不涉及真实发送。</p>}<label htmlFor="message">家长消息</label><textarea id="message" value={message} onChange={e=>setMessage(e.target.value)} maxLength={5000} required placeholder="例如：孩子不愿意坚持阅读，该怎么办？"/>
      <div className="quick-input">{[['价格异议','这个课程可以按月购买吗？'],['效果质疑','孩子阅读效果不明显，怎么办？'],['退款投诉','我要退款，请尽快处理。'],['正常咨询','这个课程适合几岁的孩子？']].map(([title,content])=><button key={title} type="button" onClick={()=>setMessage(content)}>{title}</button>)}</div>
      <button className="button primary full" disabled={ctx.busy}>{ctx.busy?'正在生成并审核…':'生成并审核回复'} <ArrowRight size={16}/></button><p className="muted">不通过审核或高风险内容进入人工处理，系统不会自动对外发送。</p></form></Panel>
      <Panel title="执行结果" description={ticket?.id||'等待任务'}>{ticket?<><div className="record-head"><StatusBadge status={ticket.review?.status}/></div><Block title="家长消息" value={ticket.message}/><Block title="前台初稿" value={ticket.draft}/><Block title="合规审核" value={ticket.review?.reason||ticket.review_history?.map(h=>'第 '+h.round+' 轮：'+(h.violations||[]).map(v=>v.type+' '+(v.original||'')).join('、')).join('\n')||'缺少审核信息'}/><Block title="风险与处置" value={(ticket.risk_level||'未知')+' · '+(ticket.risk_reason||'')+'\n'+(ticket.action||'')}/><Block title="最终回复" value={ticket.review?.status==='PASS'?(ticket.reply||'尚未获准交付'):'未通过审核或历史未验证记录，不可作为交付凭证。'}/>{ticket.reply && <button className="button outline" type="button" onClick={()=>navigator.clipboard.writeText(ticket.reply)}>复制回复</button>}<p className="muted">交付状态：{ticket.delivery_status === 'NOT_SENT' ? '未发送' : (ticket.delivery_status || '历史记录未确认')}。系统不发送消息。</p><details><summary>参考知识与审核过程</summary><Block title="知识来源" value={ticket.knowledge_sources?.map(x=>x.question || x.id).join('\n') || '未找到直接匹配的参考资料，或历史记录未保存来源。'}/></details></>:<Empty title="等待业务事件" description="提交家长消息后，执行结果将展示在这里。"/>}</Panel>
    </div>
    <section className="ticket-history-section" aria-label="工单历史">
      <Panel title="历史工单" description={ctx.tickets.length ? '选择记录，查看对应的消息、审核和最终回复（最近 30 条）' : '工单处理后会自动出现在这里'}>
        {ctx.tickets.length
          ? <div className="ticket-history-list">{ctx.tickets.slice(0,30).map((item,index) =>
              <button type="button" key={item.id||index}
                className={'ticket-history-item'+(ticket?.id===item.id?' active':'')}
                aria-pressed={ticket?.id===item.id}
                onClick={() => { ctx.setSelectedTicketId(item.id); ctx.setTicket(item); }}>
                <span className="ticket-history-title">{item.message||item.id||'历史工单'}</span>
                <small>{item.time||'未提供时间'} · {item.risk_level||'未分级'}</small>
                <ChevronRight size={16}/>
              </button>)}</div>
          : <Empty title="暂无历史工单" description="提交第一条家长消息后就可以在这里查看。"/>}
      </Panel>
    </section>
    <Interrupted kind="ticket" ctx={ctx}/>
  </>;
}

export function Operations({ ctx }) {
  const days=ctx.data?.sop_days||[];
  const options=days.map(d=>typeof d==='string'?d:d.day||d.name).filter(Boolean);
  const [day,setDay]=useState('');
  const selectedDay=options.includes(day)?day:options[0]||'';
  const pkg=ctx.packageRecord||ctx.packages[0];
  const tasks=pkg?.tasks||[];
  function generate(e){e.preventDefault();if(selectedDay)ctx.run('/api/sop',{day:selectedDay},r=>{const p=r.package||r;ctx.setPackageRecord({...p,id:p.id||(p.path||'').split(/[\\/]/).pop().replace(/\.md$/,'')})});}
  return <><PageHeading kicker="SOP MANAGEMENT" title="SOP 管理" description="按营期 SOP 准备日度运营内容，并逐项核对审核结果。"/>
    <div className="form-grid"><Panel title="生成运营包" description="选择营期日，生成并审核任务"><form onSubmit={generate} className="field-stack"><label htmlFor="sop-day">营期日</label><select id="sop-day" value={selectedDay} onChange={e=>setDay(e.target.value)} required>{options.length?options.map(d=><option key={d} value={d}>{d}</option>):<option value="">暂无可用 SOP</option>}</select><p className="muted">每项任务独立审核；未通过或缺项的运营包不可交付。</p><button className="button primary full" disabled={ctx.busy||!options.length}>生成当日运营包 <ArrowRight size={16}/></button></form></Panel>
    <Panel title="运营包详情" description={pkg?.day||'当前尚无记录'}>{pkg?<><StatusBadge status={pkg.status||pkg.decision?.status}/>{packageMaterial(pkg)&&<button className="button outline" onClick={()=>navigator.clipboard.writeText(packageMaterial(pkg))}>复制运营材料</button>}<p className="muted">批准只表示内容获准，实际发布仍需人工执行。</p>{tasks.length?tasks.map((t,i)=><div className="record" key={i}><div className="record-head"><strong>任务 {i+1} · {t.task?.time||''} {t.task?.channel||''}</strong><StatusBadge status={t.review?.status}/></div><p>{t.task?.audience||''}</p><div className="prose">{t.review?.content||t.review?.reason||'暂无内容'}</div></div>):<Block title="运营内容" value={pkg.content||'暂无结构化任务记录'}/>}</>:<Empty title="暂无运营包" description="选择营期日开始生成。"/>}</Panel></div><Interrupted kind="package" ctx={ctx}/>
  </>;
}

export function Growth({ ctx }) {
  const w=ctx.workflow||{}, a=w.analysis||{}, runs=(w.runs||[]).filter(r=>r.type==='FOLLOWUP_BATCH');
  const batch=ctx.batch||runs[0]?.id||'',run=runs.find(r=>r.id===batch),tasks=(w.tasks||[]).filter(t=>t.batch_id===batch),artifact=(w.artifacts||[]).find(t=>t.batch_id===batch),approval=(w.approvals||[]).find(t=>t.batch_id===batch),trace=(w.trace||[]).filter(t=>t.run_id===batch),drafts=(w.drafts||[]).filter(d=>tasks.some(t=>t.id===d.task_id));
  let review={};try{review=typeof artifact?.review==='string'?JSON.parse(artifact.review):artifact?.review||{}}catch{review={};}
  const eligible=tasks.filter(t=>t.status==='WAITING_CONTENT');
  const recipients=artifact?.approval_recipients;
  const canApprove=!!artifact?.material_hash&&review.status==='PASS'&&Array.isArray(recipients)&&recipients.length>0;
  const workflowAction=(action,decision)=>{const body=(action==='seed'||action==='plan')?{}:(action==='content')?{batch_id:batch}:(action==='approve')?{batch_id:batch,artifact_id:artifact?.id,decision,material_hash:artifact?.material_hash}:{batch_id:batch,artifact_id:artifact?.id};ctx.run('/api/workflow/'+action,body,r=>{if(action==='plan')ctx.setBatch(r.batch_id)});};
  return <><PageHeading kicker="LEAD FOLLOW-UP" title="跟进线索" description="查看客户分层与跟进建议；经人工审批后生成本地草稿和模拟反馈。"/>
    <div className="info-note">模拟演示：示例客户与互动事件是合成数据，系统不连接真实发送渠道。</div>
    <div className="metric-grid"><Metric title="客户记录" value={a.total??0} hint="包含模拟和入站客户" icon={UsersRound}/><Metric title="三天未互动" value={a.inactive??0} hint="基于最近互动日期" icon={CalendarDays}/><Metric title="跟进批次" value={runs.length} hint="已规划记录" icon={ChartNoAxesCombined}/><Metric title="本地草稿" value={(w.drafts||[]).length} hint="未对外发送" icon={FileText}/></div>
    <div className="workspace-grid"><Panel title="01 / 数据增长 · 数据分析" description={a.definition||'尚无分析数据'}><div className="action-row"><button className="button outline" disabled={ctx.busy} onClick={()=>workflowAction('seed')}>载入模拟客户</button><button className="button primary" disabled={ctx.busy||!a.total} onClick={()=>ctx.run('/api/workflow/plan-content',{},r=>ctx.setBatch(r.batch_id))}>生成跟进计划并审核内容 <ArrowRight size={15}/></button></div><p className="muted">统计日期：{a.as_of||'—'}。同意状态和触达次数会影响行动。{!a.total && '请先载入模拟客户或创建入站客户。'}</p></Panel>
    <Panel title="02 / 数据增长 · 选择批次" description="计划依据真实存储的模拟数据生成"><div className="field-stack"><select aria-label="选择跟进批次" value={batch} onChange={e=>ctx.setBatch(e.target.value)}><option value="">选择批次</option>{runs.map(r=><option key={r.id} value={r.id}>{r.id} · {statusLabel(r.status)}</option>)}</select></div><Block title="批次状态" value={run?.status||'尚未选择批次'}/></Panel></div>
    <div className="workspace-grid growth-grid"><Panel title="任务与协作记录" description="根据同意状态、频次与互动确定行动">{tasks.length?tasks.map(t=><div key={t.id} className="record"><div className="record-head"><strong>{t.customer_id} · {t.action}</strong><StatusBadge status={t.status}/></div><p>{t.reason}</p><small>{t.owner}</small></div>):<Empty title="暂无任务" description="先载入模拟客户，再制定跟进计划。"/>}<Block title="协作轨迹" value={trace.slice().reverse().map(t=>t.owner+' · '+t.action+' · '+statusLabel(t.status)+'\n'+t.at).join('\n\n')||'暂无记录'}/></Panel>
    <div className="panel-stack"><Panel title="03 / 服务运营 · 内容与审核" description="生成内容并进行独立审核"><button className="button outline" disabled={ctx.busy||!eligible.length} onClick={()=>workflowAction('content')}>生成并审核内容</button><Block title="当前版本" value={artifact?.content||'尚未生成内容'}/><Block title="审核结果" value={statusLabel(review.status)+'\n'+(review.reason||'')}/></Panel>
    <Panel title="04 / 经营者 · 审批" description="批准正文和完整名单"><StatusBadge status={approval?.status||'PENDING'}/><Block title="待审批名单" value={Array.isArray(recipients)?recipients.length+' 人\n'+recipients.join('\n'):'当前无可验证的完整名单'}/><div className="action-row"><button className="button primary" disabled={ctx.busy||!canApprove} onClick={()=>workflowAction('approve','APPROVED')}>批准内容和名单</button><button className="button danger" disabled={ctx.busy||!canApprove} onClick={()=>workflowAction('approve','REJECTED')}>打回</button></div><p className="muted">批准与当前版本及完整名单绑定，不能自动对外发送。</p></Panel>
    <Panel title="05 / 服务运营 · 草稿与反馈" description="仅本地草稿和模拟回执"><button className="button outline" disabled={ctx.busy||approval?.status!=='APPROVED'||!eligible.length} onClick={()=>workflowAction('queue')}>创建本地草稿</button>{drafts.length?drafts.map(d=><div key={d.id} className="record"><div className="record-head"><strong>{d.id}</strong><StatusBadge status={d.status}/></div><p>任务 {d.task_id}</p><button className="button subtle" disabled={ctx.busy||d.status!=='DRAFT'} onClick={()=>ctx.run('/api/workflow/receipt',{draft_id:d.id})}>记录模拟回执</button></div>):<p className="muted">暂无草稿。</p>}</Panel></div></div>
  </>;
}

function HumanTaskForm({ item, canResolve, busy, run }) {
  // Keyed by task identity so a note cannot carry over to another approval item.
  const [result, setResult] = useState('');
  return <form className="field-stack human-form" onSubmit={event=>{
    event.preventDefault();
    if(result.trim())run('/api/human-tasks',{id:item.id,result:result.trim()},()=>setResult(''));
  }}>
    <label htmlFor="human-note">人工处理 · {item.human_task.owner||'负责人'}</label>
    <textarea id="human-note" maxLength={5000} required value={result} disabled={!canResolve}
      onChange={event=>setResult(event.target.value)} placeholder="填写人工处理结果"/>
    <button className="button outline" disabled={busy||!canResolve}>记录并完成任务</button>
    <p className="muted">记录处理结果不代表已发送消息或已退款。</p>
  </form>;
}

export function Risk({ ctx }) {
  const items=ctx.approvals,selected=items.find((x,i)=>String(x.id??i)===String(ctx.selected))||items[0];
  const material=selected?.kind==='package'?packageMaterial(selected):null;
  const canReject=selected?.kind==='growth' ? !!selected.material_hash : !!selected?.content_hash&&(selected.kind==='ticket'?selected.gate7==='PENDING':selected.status==='PENDING_APPROVAL'&&material!==null);
  const canApprove=canReject&&(selected.kind!=='ticket'||selected.review?.status==='PASS');
  const human=selected?.kind==='ticket'&&selected.human_task?.status==='PENDING';
  const canResolve=human&&(selected.risk_level!=='L3'||['APPROVED','REJECTED','REVIEW_REQUIRED'].includes(selected.gate7));
  const history=ctx.packages.filter(p=>p.status!=='PENDING_APPROVAL');
  const decide=decision=>selected.kind==='growth' ? ctx.run('/api/workflow/approve',{batch_id:selected.batch_id,artifact_id:selected.id,decision:decision==='approve'?'APPROVED':'REJECTED',material_hash:selected.material_hash}) : ctx.run('/api/approvals',{kind:selected.kind,id:selected.id,decision,content_hash:selected.content_hash});
  return <><PageHeading kicker="RISK & APPROVAL" title="风控与审批" description="高风险事项与未通过审核的内容，交由人类经营者决策。"/>
    <div className="form-grid"><Panel title="待处理队列" description={items.length+' 项需要关注'}>{items.length?items.map((item,i)=><button className={'select-record'+(selected===item?' selected':'')} key={item.kind+String(item.id??i)} onClick={()=>ctx.setSelected(String(item.id??i))}><div className="record-head"><strong>{item.title||item.id||'待处理事项'}</strong><StatusBadge status={item.status}/></div><p>{item.summary||item.message||item.reason||'需要人工处理'}</p><small>{item.time||''}</small></button>):<Empty title="队列已清空" description="目前没有待处理事项。"/>}</Panel>
    <Panel title="事项详情" description="核对材料后作出决定">{selected?<><StatusBadge status={selected.status||'PENDING'}/><Block title="事件原文" value={selected.message||selected.summary}/><Block title="风险分析" value={selected.reason||selected.risk_reason}/><Block title="Agent 建议" value={selected.advice||selected.escalation}/>{selected.kind==='growth'&&<Block title="完整候选名单" value={(selected.recipients||[]).join('\n')}/>}<Block title={selected.kind==='package'?'完整审批材料':'待审内容'} value={selected.kind==='package'?(material||'材料字段不完整，无法核验。'):(selected.content||selected.reply||selected.review_candidate)}/><div className="action-row"><button className="button primary" disabled={ctx.busy||!canApprove} onClick={()=>decide('approve')}>批准</button><button className="button danger" disabled={ctx.busy||!canReject} onClick={()=>decide('reject')}>打回</button></div><p className="muted">{canApprove?'审批绑定当前材料，不会自动发送。':canReject?'审核未通过，可打回，不能批准。':'当前事项不可审批。'}</p>
      {selected.kind==='growth'&&<button className="button outline" onClick={()=>{ctx.setBatch(selected.batch_id);ctx.go('growth')}}>返回跟进计划并创建本地草稿</button>}{human&&<HumanTaskForm key={selected.kind+'-'+selected.id} item={selected} canResolve={canResolve} busy={ctx.busy} run={ctx.run}/>} </>:<Empty title="选择一个事项" description="在左侧选择需要人工处理的事件。"/>}</Panel></div>
    <h2 className="section-small-title">运营包历史结果</h2><Panel title="历史运营包" description="不计入待处理队列">{history.length?history.map(p=><div className="record" key={p.id}><div className="record-head"><strong>{p.day||p.id}</strong><StatusBadge status={p.status}/></div><p>记录编号：{p.id}</p></div>):<Empty title="暂无历史结果" description="已处理或未完成的运营包将显示在这里。"/>}</Panel>
  </>;
}

export function Analytics({ ctx }) {
  const total=ctx.tickets.length,counts=['L1','L2','L3'].map(l=>ctx.tickets.filter(t=>t.risk_level===l).length);
  const gradedTotal=counts.reduce((sum,n)=>sum+n,0);
  return <><PageHeading kicker="BUSINESS INTELLIGENCE" title="经营分析" description="用可核对的本地记录理解业务与人工介入情况。" action={<button className="button outline" disabled={ctx.busy} onClick={()=>ctx.run('/api/report',{},r=>ctx.setReport(r.report||r.content||r))}>生成经营周报 <ArrowUpRight size={16}/></button>}/>
    <div className="metric-grid"><Metric title="工单总数" value={total} hint="全部本地工单" icon={ClipboardList}/><Metric title="L3 高风险" value={counts[2]} hint="按已归档工单" icon={ShieldCheck}/><Metric title="待人工处理" value={ctx.approvals.length} hint="当前队列" icon={UsersRound}/><Metric title="运营包" value={ctx.packages.length} hint="本地记录数" icon={BookOpen}/></div>
    <div className="workspace-grid"><Panel title="风险等级分布" description="不包含无等级记录">{counts.map((n,i)=><div className="risk-bar-row" key={i}><span>L{i+1}</span><div className="risk-bar"><i style={{width:(gradedTotal?n/gradedTotal*100:0)+'%'}}/></div><strong>{n}</strong></div>)}<p className="muted">已分级：{gradedTotal} / 总工单：{total} · 当前本地记录</p></Panel><Panel title="经营周报" description="最近七日的结构化工单"><div className="prose report-content">{typeof (ctx.report||ctx.data?.report)==='string'?(ctx.report||ctx.data?.report):'点击上方按钮生成周报。'}</div></Panel></div>
  </>;
}


export function Customers({ctx}) {
  const customers=ctx.workflow?.analysis?.customers||[];
  const [id,setId]=useState('');
  const [stage,setStage]=useState('训练营');
  const [reason,setReason]=useState('');
  const [source,setSource]=useState('');
  const customer=customers.find(c=>c.customer_id===id)||customers[0];
  const history=(ctx.workflow?.events||[]).filter(e=>e.customer_id===customer?.customer_id);
  const changes=(ctx.workflow?.consent_changes||[]).filter(e=>e.customer_id===customer?.customer_id);
  const stages=(ctx.workflow?.state_changes||[]).filter(e=>e.customer_id===customer?.customer_id);
  const updateStage=e=>{e.preventDefault();ctx.run('/api/customers/stage',{customer_id:customer.customer_id,stage,reason},()=>setReason(''));};
  const consent=value=>ctx.run('/api/customers/consent',{customer_id:customer.customer_id,consent:value,source},()=>setSource(''));
  return <><PageHeading kicker="CUSTOMER PROFILE" title="客户画像" description="查看客户阶段、授权状态和互动记录，人工维护客户信息。"/>
    <div className="form-grid"><Panel title="客户列表" description="来源为模拟的客户仅用于演示">{customers.length?customers.map(c=><button className={'select-record'+(customer?.customer_id===c.customer_id?' selected':'')} key={c.customer_id} onClick={()=>setId(c.customer_id)}><strong>{c.customer_id}</strong><p>{c.source} · {c.stage} · {c.consent?'已记录同意':'未记录同意'}</p></button>):<Empty title="暂无客户" description="处理家长消息时可创建入站客户，也可在客户跟进中载入模拟数据。"/>}</Panel>
    <Panel title="客户详情" description={customer?.customer_id}>{customer&&<><Block title="来源与互动" value={customer.source+' · 最近互动：'+(customer.last_interaction||'无记录')+' · 近七日模拟触达：'+customer.contacts_7d}/><form className="field-stack" onSubmit={updateStage}><label>客户阶段</label><select value={stage} onChange={e=>setStage(e.target.value)}><option>承接期</option><option>训练营</option><option>已结束</option></select><label>变更依据</label><input required value={reason} onChange={e=>setReason(e.target.value)} placeholder="填写人工确认依据"/><button className="button outline" disabled={ctx.busy}>记录阶段变更</button></form><div className="field-stack"><label>授权来源或撤销依据</label><input value={source} onChange={e=>setSource(e.target.value)} placeholder="例如家长明确同意的记录"/><div className="action-row"><button className="button outline" disabled={ctx.busy||!source.trim()} onClick={()=>consent(true)}>记录同意</button><button className="button outline" disabled={ctx.busy||!source.trim()} onClick={()=>consent(false)}>撤销同意</button></div><p className="muted">须填写来源或撤销依据；撤销后将阻止尚未执行的主动触达。已有历史授权来源未知时请重新核实。</p></div><Block title="授权记录" value={changes.map(x=>x.at+' · '+(x.consent?'同意':'撤销')+' · '+x.source).join('\n')||'暂无可追溯记录'}/><Block title="阶段记录" value={stages.map(x=>x.at+' · '+x.old_stage+' → '+x.new_stage+' · '+x.reason).join('\n')||'暂无变更记录'}/><Block title="互动历史" value={history.map(x=>x.occurred_at+' · '+x.type+' · '+x.source).join('\n')||'暂无互动记录'}/><button className="button outline" onClick={()=>ctx.go('growth')}>进入客户跟进</button></>}</Panel></div></>;
}

export function Reports({ ctx }) {
  const date = new Intl.DateTimeFormat('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()).replaceAll('/', '-');
  const tickets = ctx.tickets || [];
  const highIntent = (ctx.workflow?.analysis?.customers || []).filter(customer => customer.segment === '高意向').length;
  const customers = ctx.workflow?.analysis?.customers || [];
  const risks = tickets.filter(ticket => ticket.risk_level === 'L3').length;
  const today = new Date().toDateString();
  const todayTickets = tickets.filter(ticket => {
    const created = new Date(ticket.time || ticket.created_at || '');
    return !Number.isNaN(created.getTime()) && created.toDateString() === today;
  });
  const [dailyReport, setDailyReport] = useState('');
  const generateReport = () => setDailyReport([
    date + ' 私域运营日结',
    '',
    '今日有效会话：' + todayTickets.length,
    '当前客户记录：' + customers.length,
    '高意向客户：' + highIntent,
    '高风险会话：' + todayTickets.filter(ticket => ticket.risk_level === 'L3').length,
    '待人工处理：' + ctx.approvals.length,
    '运营内容包：' + (ctx.packages || []).length,
    '',
    '数据来源：本地工作空间记录。该报告为当前页面汇总，不会发送消息或执行外部操作。'
  ].join('\n'));
  return <>
    <PageHeading kicker="DAILY REPORT" title="日结报告" description="汇总当前本地记录，生成可核对的运营复盘。" action={<button className="button primary" onClick={generateReport}>生成今日日报 <ArrowUpRight size={16}/></button>}/>
    <section className="report-banner"><div><span>运营日期</span><strong>{date}</strong><p>数据来源：当前工作空间的本地记录</p></div><FileText size={34} strokeWidth={1.4}/></section>
    <div className="metric-grid">
      <Metric title="今日有效会话" value={todayTickets.length} hint="按本地时间统计" icon={MessageCircle}/>
      <Metric title="高意向客户" value={highIntent} hint="当前客户样本" icon={UsersRound}/>
      <Metric title="高风险事项" value={risks} hint="L3 风险工单" icon={ShieldCheck}/>
      <Metric title="待人工处理" value={ctx.approvals.length} hint="审批与复核队列" icon={ClipboardList}/>
    </div>
    <Panel title="日结复盘" description="由本地运营记录生成；没有报告时可点击右上角生成。">
      {dailyReport ? <div className="prose report-content">{dailyReport}</div> : <Empty title="日报尚未生成" description="生成后会在这里展示会话、运营和待处理事项的复盘内容。"/>}
    </Panel>
  </>;
}

const clientReply = message => {
  const text = message.toLowerCase();
  if (/价格|多少钱|费用|购买|报名/.test(text)) return '您好，课程安排和费用会根据孩子的年龄与学习情况来确认。您可以告诉我孩子现在几年级、平时的阅读习惯，我帮您看看适合的方案。';
  if (/试听|体验|试课/.test(text)) return '可以先了解一下体验课。您方便说下孩子的年龄和比较合适的时间吗？我帮您确认近期安排。';
  if (/退款|投诉|不满|退费/.test(text)) return '收到您的情况了，我先帮您登记并请课程顾问尽快跟进。方便留一下孩子的姓名或报名手机号后四位吗？';
  return '您好，感谢您来咨询。为了给您更合适的建议，可以先告诉我孩子的年龄，以及目前最想改善的学习问题吗？';
};

export function ClientDemo() {
  const [messages, setMessages] = useState([
    { from: 'consultant', text: '您好，我是王老师。想先了解一下孩子目前的阅读情况吗？' }
  ]);
  const [draft, setDraft] = useState('');
  const sendMessage = event => {
    event.preventDefault();
    const message = draft.trim();
    if (!message) return;
    setMessages(current => [...current, { from: 'parent', text: message }, { from: 'consultant', text: clientReply(message) }]);
    setDraft('');
  };
  return <>
    <PageHeading kicker="CLIENT PREVIEW" title="客户端模拟" description="预览家长看到的咨询界面与统一回复。"/>
    <div className="info-note">此页面只在浏览器中模拟对话，不会连接客户资料或发送真实消息。</div>
    <div className="client-demo-layout">
      <Panel title="王老师 · 课程顾问" description="伴学课程咨询">
        <div className="client-chat" aria-live="polite">
          {messages.map((message, index) => <div key={index} className={'client-message ' + message.from}>
            <span className="client-avatar">{message.from === 'parent' ? '我' : '王'}</span>
            <p>{message.text}</p>
          </div>)}
        </div>
        <form className="client-compose" onSubmit={sendMessage}>
          <input aria-label="输入模拟咨询" maxLength={500} value={draft} onChange={event => setDraft(event.target.value)} placeholder="输入一条模拟咨询…"/>
          <button className="button primary" disabled={!draft.trim()} aria-label="发送模拟消息"><Send size={16}/></button>
        </form>
      </Panel>
      <Panel title="快捷咨询" description="点击填入不同的模拟问题">
        <div className="client-prompts">{['课程适合多大孩子？','可以先试听吗？','课程费用是多少？','我想申请退款'].map(prompt => <button key={prompt} type="button" onClick={() => setDraft(prompt)}>{prompt}<ArrowRight size={14}/></button>)}</div>
        <p className="muted">模拟回复仅用于界面演示，不代表真实课程承诺或正式服务答复。</p>
      </Panel>
    </div>
  </>;
}
