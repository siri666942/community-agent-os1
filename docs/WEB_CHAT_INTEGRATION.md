# Web Chat ↔ Agent Service 对接调试说明

面向 Web Chat(前端)同学的联调指南。接口契约细节见 [API.md](./API.md),本文侧重**怎么跑起来、怎么联调、页面怎么接**。

## 1. 架构与分工

```
用户(家长/老师) ↔ Web Chat(你们) ↔ Agent Service(本服务,8080) ↔ Database(MySQL/本地 SQLite)
```

- Agent Service 是唯一的 AI 能力层:出稿、质检、画像、分层、SOP 全在这里,**前端不需要调任何 LLM**
- **只出稿不发送**:服务端没有自动外发路径,所有发送由老师在 Web 端点击触发,发送动作回调 `POST /api/v1/send` 留痕
- 所有接口 `application/json; charset=utf-8`,已开 CORS(`Access-Control-Allow-Origin: *`),开发期跨端口直连即可

## 2. 快速跑起来

```bash
# ① 准备数据(首次):Excel → SQLite,约 2 分钟,产出 service/data/customers.db
python3 -I scripts/import_excel.py

# ② 启动 Agent Service(默认 127.0.0.1:8080)
python3 -m service.app

# ③ 健康检查
curl http://127.0.0.1:8080/healthz
# {"ok": true, "service": "agent-service", "db": ".../customers.db", "llm": false}
```

环境变量:

| 变量 | 默认 | 说明 |
|---|---|---|
| `OPC_SERVICE_HOST` / `OPC_SERVICE_PORT` | `127.0.0.1` / `8080` | 监听地址 |
| `OPC_SERVICE_LLM` | `off` | `on` 时备选稿由 LLM 生成;**off 时走确定性模板**,接口结构完全一致,联调建议先用 off(稳定、可断网) |

## 3. 通用约定

- **请求**:`Content-Type: application/json`;uid 均为字符串(如 `"703971"`)
- **成功**:一律 `200` + JSON 体
- **错误**:非 200,体为 `{"error": "..."}`;`409` 另带质检明细(见 §4)
- **404**:`{"error": "customer xxx not found"}` / `{"error": "not found"}`
- 时间字段 ISO8601(如 `"2026-11-08T10:30:00"`)

## 4. 对话页(核心链路,建议最先联调)

老师工作台「接待家长」的完整闭环:

```
家长消息 ──POST /api/v1/drafts──▶ 三个备选(A/B/C)+ 逐条风险标注
老师选用/改写 ──POST /api/v1/qc──▶ 发送前预检(可选,用于按钮状态)
老师点发送 ──POST /api/v1/send──▶ 闸门裁决 + 全程留痕
```

### 4.1 出稿 `POST /api/v1/drafts`

```json
{"uid": "703971", "message": "想问下价格怎么样，另外能约个试听吗？",
 "recent_messages": ["…上次聊天…"], "cid": "可选,续聊时传"}
```

响应(200):

```json
{
  "drafts": [
    {"id": "DR...", "variant": "A", "position": "标准口径", "text": "…",
     "qc": {"status": "green", "risks": [], "suggestion": ""}},
    {"id": "DR...", "variant": "B", "position": "推进型", "text": "…", "qc": {"status": "yellow",
     "risks": [{"type": "价格优惠承诺", "level": "yellow", "matched": "…原文…",
                "suggestion": "…合规改写建议…"}], "suggestion": "…"}}
  ],
  "customer_snapshot": {"uid": "703971", "nickname": "悦悦", "tier": "S1",
    "activity": "高", "intent": "高", "summary": "近 7 日活跃…"},
  "sop_hint": "price",
  "cid": "C..."
}
```

要点:
- `drafts` 恒为 3 条(A 标准口径 / B 推进型 / C 关系型),**逐条独立质检**,UI 上每条稿子旁边直接标状态点
- `cid`:本条家长消息已自动入库留痕,**续聊必须回传同一个 cid**,会话回放(§7)才连得上
- `customer_snapshot` 可直接渲染成对话页侧栏的画像摘要

### 4.2 发送前预检 `POST /api/v1/qc`(可选)

```json
{"text": "老师改写后的最终文案", "confirmed": false}
```

响应:`{"status": "green|yellow|red", "risks": [...], "suggestion": "…", "sendable": true|false}`
用于**实时决定发送按钮状态**,不产生留痕。

### 4.3 发送闸门 `POST /api/v1/send`

```json
{"cid": "C...", "text": "最终文案", "variant": "B",
 "edited": true, "confirmed": true, "sender": "王老师"}
```

- `variant`:选用的备选 `A|B|C`,老师自己写的传 `"CUSTOM"`
- `edited`:是否在备选基础上改写过;`confirmed`:是否勾选了「我已确认」

**响应三态(前端必须按此交互)**:

| 质检状态 | 交互 | 响应 |
|---|---|---|
| 🟢 green | 发送按钮可点 | `200 {"ok": true, "gate": {...}}` |
| 🟡 yellow | 勾选「我已确认」后才可点 | 未勾选时 `sendable: false`;勾选后 `200` |
| 🔴 red | **发送按钮置灰** | `409 {"error": "质检未通过,禁止发送", "qc_status": "red", "risks": [...], "gate": {...}}` |

`gate` 里含 `message_id / variant / edited / confirmed / sender / qc_status / qc_risks / sendable`,即留痕凭证,可用于回放展示。

## 5. 用户画像卡 `GET /api/v1/profile/{uid}`

响应五块内容(字段即 UI 模块):

```json
{
  "uid": "...", "nickname": "悦悦", "phone_masked": "133****8666",
  "activity":  {"level": "高", "active_days": 7, "avg_minutes": 24.4,
                "evidence": "近7日活跃 7 天 / 日均阅读 24.4 分钟(阈值 ≥5 天 且 ≥15 分钟)"},
  "intent":    {"level": "高", "signals": ["问价", "约试听"], "confidence": "high",
                "evidence": "近3日推进信号 2 项:问价、约试听"},
  "segment":   {"tier": "S1", "name": "S1 高价值推进"},
  "summary":   "近 7 日活跃 7 天，…",
  "tags_ai": ["高活跃度用户（…）", "高意向（…）"], "tags_manual": ["…"],
  "tier": "S1",
  "sop": {"uid": "...", "nickname": "悦悦", "stage": "课程与价格",
          "stayed_hours": 2.5, "status": "正常", "timeout": false, "suggest": "…"}
}
```

- `evidence` 全部是**人话依据**,直接展示,不需要前端二次解释
- `intent.confidence`:只有行为数据(点击/标签/测字)时为 `"low"`,UI 可加个「低置信度」角标
- **脱敏**:手机号只给打码版;逐日阅读明细不上前端

## 6. 增值分析师 `GET /api/v1/growth/daily`

```
GET /api/v1/growth/daily?limit=20          # 今日跟进名单
GET /api/v1/growth/daily?limit=20&uid=703971   # 只查一人(刷新分层/依据)
```

响应:`segments` 数组(S1/S2/S3 三桶),每桶 `count / action / script(专属话术) / customers(最多 10 条示例)`,`customers` 内含 `uid/nickname/activity/intent/evidence/summary`。

前端建议:名单页按 `tier` 分 tab,每行展示 `evidence` 两行依据,「生成话术」按钮直接用 `script` 预填到对话输入框,再走 §4 的出稿/发送链路。

`GET /api/v1/growth/report` → `{"distribution": {"S1": n, "S2": n, "S3": n}, "sampled": n}`(工作台分层卡片)。

## 7. 会话回放 `GET /api/v1/messages/{cid}`

`{"cid": "...", "messages": [...]}`,按时间正序,每条含 `role(parent|teacher)/text/created_at/sender/variant/edited/confirmed/qc_status/qc_risks`。
老师发送历史、改写与否、质检状态全部可回放——**审计场景直接用它**。

## 8. SOP 看板与人工调整

```
GET  /api/v1/sop/board?limit=20[&uid=703971]
→ 200 {"board": [{"uid", "nickname", "stage", "stayed_hours",
                  "status": "正常|超时|已停止", "timeout": true|false, "suggest": "…"}]}

POST /api/v1/sop/change
{"uid": "", "field": "stay_limit_hours", "old_value": "24", "new_value": "48",
 "reason": "本期节奏调整", "scope": "once|default|log_only", "editor": "王老师"}
→ 200 {"ok": true, "change": {...带 id、created_at}}
```

`scope` 三种生效范围:`once`(仅本次)/ `default`(改公司默认)/ `log_only`(只记录不生效)。UI 上做成下拉三选一即可。

## 9. 客户检索 `GET /api/v1/customers`

```
GET /api/v1/customers?limit=20&offset=0&search=悦悦&signup=已报名&tag_like=意向
→ 200 {"total": 123, "items": [...]}
```

items 里**不含手机号、不含逐日阅读明细**(脱敏)。给客户选择器/列表页用。

## 10. 联调排错速查

| 现象 | 原因与处理 |
|---|---|
| 跨端口请求被浏览器拦 | 服务已开 CORS;确认请求头 `Content-Type: application/json`,别用 form |
| `send` 返回 409 | 红灯文案,设计如此;按钮置灰,展示 `risks` 与 `suggestion` |
| 备选稿口吻很"模板" | `OPC_SERVICE_LLM=off` 的确定性模板,结构一致;要 LLM 稿开 `on`(需模型服务可用) |
| 画像 `intent.confidence: "low"` | 该用户暂无对话,只有行为数据,设计如此 |
| `customer xxx not found` | uid 不在库;先用 `/api/v1/customers?search=` 找一个真实 uid |
| 消息回放是空的 | `cid` 没续传;drafts 响应里的 `cid` 要存下来 |
| 改了 Excel 不生效 | 重跑 `python3 -I scripts/import_excel.py` 再重启服务 |

## 11. 可选:经 web_api 代理联调

仓库 `Community-Agent-OS1/web_api` 带 `agent-proxy` 任务(`POST /api/agent`,job 异步轮询 `GET /api/jobs/{id}`),转发同一批 `/api/v1/*` 接口,适合想顺带验证 job 机制的场景。**纯前端联调直连 8080 即可**,更快。

## 12. 建议联调顺序

1. `/healthz` 通没通
2. `/api/v1/customers` 拿一个真实 uid
3. `/api/v1/profile/{uid}` 看画像五块
4. `/api/v1/drafts` → `/api/v1/qc` → `/api/v1/send`(先绿稿、再黄稿勾确认、最后试红稿 409)
5. `/api/v1/messages/{cid}` 回放验证留痕
6. `/api/v1/growth/daily` + `/api/v1/sop/board` 补齐工作台页面

有问题直接把请求体 + 响应体甩过来,对着改最快。
