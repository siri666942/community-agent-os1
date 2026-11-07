import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToString } from 'react-dom/server';
import { createServer } from 'vite';

const vite = await createServer({
  server: { middlewareMode: true },
  // SSR smoke tests do not need Vite's asynchronous browser dependency scan.
  optimizeDeps: { noDiscovery: true, include: [] },
  appType: 'custom',
  logLevel: 'error'
});
after(async () => { await vite.close(); });

const pages = await vite.ssrLoadModule('/src/pages.jsx');
await vite.ssrLoadModule('/src/App.jsx');

const t1 = { id: 'recent', message: '最新工单示例', time: '2026-11-07T12:00:00', risk_level: 'L1', review: { status: 'PASS' } };
const t2 = { id: 'older', message: '指定历史工单示例', time: '2026-11-06T12:00:00', risk_level: 'L3', review: { status: 'PASS' } };
const ctx = {
  connected: true, connectionError: '', tickets: [t1,t2], packages: [],
  approvals: [], data: { sop_days: ['D1'], report: '' },
  workflow: {
    analysis: { customers: [], total: 0, inactive: 0 },
    runs: [], tasks: [], artifacts: [], approvals: [], drafts: [], trace: []
  },
  ticket: null, packageRecord: null, selectedTicketId: 'older', selected: null,
  batch: '', report: '', busy: false, go() {}, refresh() {}, run() {},
  openTicket() {}, setTicket() {}, setPackageRecord() {}, setSelectedTicketId() {},
  setBatch() {}, setSelected() {}, setReport() {}
};

function render(Page, props = ctx) {
  return renderToString(createElement(Page, { ctx: props }));
}

test('all seven business and editorial pages render with actual data', () => {
  for (const name of ['Home','Dashboard','Workspace','Operations','Growth','Risk','Analytics','Customers']) {
    const html = render(pages[name]);
    assert.ok(html.length > 100, name + ' should render meaningful content');
  }
});

test('dashboard includes real ticket data and a selectable recent item', () => {
  const html = render(pages.Dashboard);
  assert.match(html, /指定历史工单示例/);
  assert.match(html, /最近工单/);
  assert.match(html, /工单风险分布/);
  assert.match(html, /查看完整工单详情/);
});

test('workspace uses selected historical ticket rather than latest', () => {
  const html = render(pages.Workspace);
  assert.match(html, /指定历史工单示例/);
  assert.match(html, /ticket-history-list/);
  assert.match(html, /aria-pressed="true"/);
});

test('risk analysis excludes ungraded tickets from the graded percentage denominator', () => {
  const ungraded = { id: 'u1', message: '没有风险等级的旧记录', risk_level: null };
  const onlyOneGraded = { ...ctx, tickets: [t1, ungraded] };
  const html = render(pages.Analytics, onlyOneGraded);
  assert.match(html, /已分级：/);
  assert.match(html, /width:100%/);
});

test('all pages render empty states without data or backend connection', () => {
  const empty = { ...ctx, connected: false, connectionError: '后端暂不可用', tickets: [], approvals: [], packages: [], data: null, workflow: null, selectedTicketId: null };
  assert.match(render(pages.Dashboard, empty), /还没有工单/);
  assert.match(render(pages.Home, empty), /后端暂不可用/);
  assert.match(render(pages.Operations, empty), /暂无运营包/);
});


test('growth approvals appear only for reviewable current material', async () => {
  const { approvalItems } = await vite.ssrLoadModule('/src/lib.js');
  const artifact = { id:'a', batch_id:'b', content:'提醒', material_hash:'h', approval_recipients:['c'], review:{status:'PASS'} };
  assert.equal(approvalItems({}, {artifacts:[artifact], approvals:[]})[0].kind, 'growth');
  assert.equal(approvalItems({}, {artifacts:[artifact], approvals:[{batch_id:'b', material_hash:'h', status:'APPROVED'}]}).length, 0);
  assert.equal(approvalItems({}, {artifacts:[{...artifact, review:{status:'REVIEW_REQUIRED'}}], approvals:[]}).length, 0);
});
