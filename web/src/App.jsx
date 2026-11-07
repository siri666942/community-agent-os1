import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ArrowRight, ArrowUpRight, BookOpen, ChartNoAxesCombined, ChevronRight,
  FileBarChart, Home as HomeIcon, MessageCircle, RefreshCw, Search,
  ShieldCheck, Smartphone, Sparkles, SquareActivity, UserRound, UsersRound
} from 'lucide-react';
import { request, resolveJob, approvalItems } from './lib';
import { Home, Dashboard, Workspace, Operations, Growth, Risk, Analytics, Customers, Reports, ClientDemo } from './pages';

const menuNav = [
  { id: 'dashboard', label: '运营总览', icon: SquareActivity },
  { id: 'workspace', label: '客户会话', icon: MessageCircle },
  { id: 'customers', label: '客户画像', icon: UsersRound },
  { id: 'operations', label: 'SOP 管理', icon: BookOpen },
  { id: 'growth', label: '跟进线索', icon: Sparkles },
  { id: 'reports', label: '日结报告', icon: FileBarChart },
  { id: 'client-demo', label: '客户端模拟', icon: Smartphone }
];

const generalNav = [
  { id: 'risk', label: '风控与审批', icon: ShieldCheck },
  { id: 'analytics', label: '经营分析', icon: ChartNoAxesCombined },
  { id: 'home', label: '品牌首页', icon: HomeIcon }
];
const nav = [...menuNav, ...generalNav];

const pageFromHash = () => {
  const id = window.location.hash.slice(1);
  return nav.some(item => item.id === id) ? id : 'dashboard';
};

export default function App() {
  const [page, setPage] = useState(pageFromHash);
  const [data, setData] = useState(null);
  const [workflow, setWorkflow] = useState(null);
  const [ticket, setTicket] = useState(null);
  const [packageRecord, setPackageRecord] = useState(null);
  const [report, setReport] = useState('');
  const [selected, setSelected] = useState(null);
  const [batch, setBatch] = useState('');
  const [error, setError] = useState('');
  const [dataError, setDataError] = useState('');
  const [workflowError, setWorkflowError] = useState('');
  const [selectedTicketId, setSelectedTicketId] = useState(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');
  const [demo, setDemo] = useState(false);

  const refresh = useCallback(async () => {
    // Independent requests: a workflow failure must not hide the ticket dashboard.
    const [stateResult, workflowResult] = await Promise.allSettled([
      request('/api/state'), request('/api/workflow')
    ]);
    if (stateResult.status === 'fulfilled') {
      const nextData = stateResult.value;
      setData(nextData);
      setDataError('');
      setTicket(previous => previous?.id
        ? nextData.tickets?.find(item => item.id === previous.id) || previous
        : previous);
      setPackageRecord(previous => previous?.id
        ? nextData.packages?.find(item => item.id === previous.id) || previous
        : previous);
    } else {
      setData(null);
      setDataError('工单服务读取失败：' + stateResult.reason.message);
    }
    if (workflowResult.status === 'fulfilled') {
      setWorkflow(workflowResult.value);
      setWorkflowError('');
    } else {
      setWorkflow(null);
      setWorkflowError('增长服务读取失败：' + workflowResult.reason.message);
    }
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { if (!busy) return; const timer = setInterval(refresh, 3000); return () => clearInterval(timer); }, [busy, refresh]);
  useEffect(() => {
    const sync = () => setPage(pageFromHash());
    window.addEventListener('popstate', sync);
    window.addEventListener('hashchange', sync);
    return () => {
      window.removeEventListener('popstate', sync);
      window.removeEventListener('hashchange', sync);
    };
  }, []);
  useEffect(() => {
    if (!notice) return;
    const timer = setTimeout(() => setNotice(''), 3200);
    return () => clearTimeout(timer);
  }, [notice]);

  const go = id => {
    if (!nav.some(item => item.id === id)) return;
    if (page !== id) window.history.pushState(null, '', '#' + id);
    setPage(id);
    setSearch('');
    setError('');
    window.scrollTo(0, 0);
  };

  const openTicket = id => {
    setSelectedTicketId(id);
    go('workspace');
  };

  const run = async (path, body, onSuccess) => {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      const result = await resolveJob(await request(path, body));
      onSuccess?.(result);
      await refresh();
      setNotice(path.includes('service') ? '客服任务已处理，请查看审核状态' : path.includes('sop') ? '运营任务已处理，请查看逐条结果' : path.includes('approve') || path.includes('approvals') ? '审批决定已记录' : '本地记录已更新');
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setBusy(false);
    }
  };

  const tickets = data?.tickets || [];
  const packages = data?.packages || [];
  const approvals = useMemo(() => approvalItems(data, workflow), [data, workflow]);
  const connectionError = [dataError, workflowError].filter(Boolean).join('；');
  const ctx = {
    page, go, data, workflow, tickets, packages, approvals,
    connected: !!data && !dataError, connectionError,
    busy, error, refresh, run, ticket, setTicket, packageRecord,
    setPackageRecord, report, setReport, selected, setSelected, batch, setBatch,
    selectedTicketId, setSelectedTicketId, openTicket, demo, setDemo
  };
  const components = {
    home: Home, dashboard: Dashboard, workspace: Workspace, growth: Growth,
    operations: Operations, risk: Risk, analytics: Analytics, customers: Customers,
    reports: Reports, 'client-demo': ClientDemo
  };
  const Page = components[page] || Home;
  const matches = search.trim() ? nav.filter(item => item.label.toLowerCase().includes(search.trim().toLowerCase())) : [];
  const section = (items) => items.map(({ id, label, icon: Icon }) => (
    <button className={'nav-item' + (page === id ? ' active' : '')}
      key={id} type="button" onClick={() => go(id)} aria-current={page === id ? 'page' : undefined}>
      <Icon size={19} strokeWidth={1.7}/><span>{label}</span>
      {id === 'risk' && approvals.length > 0 && <b className="nav-counter">{approvals.length}</b>}
    </button>
  ));

  if (page === 'home') return <>
    <Page ctx={ctx}/>
    {notice && <div className="toast" role="status">{notice}</div>}
  </>;

  return <div className="dashboard-backdrop">
    <div className="app-shell">
      <aside className="app-sidebar">
        <button className="sidebar-brand" type="button" onClick={() => go('home')}>
          <span className="brand-symbol"><Sparkles size={24} strokeWidth={1.6}/></span>
          <span><strong>私域合伙人</strong><small>PRIVATE DOMAIN WORKSPACE</small></span>
        </button>
        <div className="sidebar-divider">MENU</div>
        <nav className="sidebar-nav" aria-label="工作空间主导航">
          {section(menuNav)}
        </nav>
        <div className="sidebar-divider general-heading">GENERAL</div>
        <nav className="sidebar-nav" aria-label="工作空间其他导航">
          {section(generalNav)}
        </nav>
        <div className="sidebar-footer">
          <span className="sidebar-user"><UserRound size={20}/></span>
          <span><strong>人类经营者</strong><small>OWNER · HUMAN IN THE LOOP</small></span>
          <span className={'connection-dot' + (connectionError ? ' disconnected' : '')} title={connectionError ? '本地后端未连接' : '本地数据连接正常'}/>
        </div>
      </aside>
      <div className="workspace-main">
        <header className="workspace-topbar">
          <div className="breadcrumb"><span>OPC Workspace</span><ChevronRight size={15}/><strong>{nav.find(item => item.id === page)?.label}</strong></div>
          <div className="workspace-top-actions">
            <div className="top-search">
              <Search size={17}/>
              <input aria-label="搜索功能页面" placeholder="搜索功能页面..." value={search}
                onChange={event => setSearch(event.target.value)}
                onKeyDown={event => { if (event.key === 'Enter' && matches.length) go(matches[0].id); if (event.key === 'Escape') setSearch(''); }}/>
              {search && <div className="search-suggestions" role="listbox">
                {matches.length ? matches.map(({ id, label }) => <button key={id} type="button" onClick={() => go(id)} role="option" aria-selected={false}>{label}<ArrowUpRight size={14}/></button>) : <span>未找到匹配的页面</span>}
              </div>}
            </div>
            <button className="icon-button" type="button" disabled={busy} onClick={refresh} title="刷新数据" aria-label="刷新数据"><RefreshCw size={19}/></button>
            <button className="button dark top-action" type="button" onClick={() => go('workspace')}>进入客户会话 <ArrowRight size={15}/></button>
          </div>
        </header>
        <main className="workspace-content">
          {connectionError && <div className="error-note" role="alert">{connectionError}。<button type="button" onClick={refresh}>重新连接</button></div>}
          {error && <div className="error-note" role="alert">{error}</div>}
          <Page ctx={ctx}/>
        </main>
        <footer className="workspace-footer"><span>OPC MISSION CONTROL</span><span>JUNCTION CHINA 2026</span></footer>
      </div>
    </div>
    {notice && <div className="toast" role="status">{notice}</div>}
  </div>;
}
