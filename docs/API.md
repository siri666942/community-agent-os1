# Agent Service RESTful 接口契约 v1

> 三层架构:**用户 ↔ Web Chat ↔ Agent Service(本文档)↔ Database**
> 协作:北邮 + 北方工大(Web Chat + Database)× Friday(Agent Service)
> 所有接口 `Content-Type: application/json; charset=utf-8`,已开 CORS。

## 0. 设计红线(与 OPSIE 对齐)

1. **本服务只出稿、不发送**。任何对外消息必须由 Web 端老师点击「发送」后调用 `POST /api/v1/send` 留痕;系统无自动外发路径。
2. **红色质检状态禁止发送**:`send` 接口对红稿返回 `409`,Web 端须置灰发送按钮。
3. **手机号脱敏**:服务端只存 `133****8666` 形式,接口不下发明文手机号。
4. 确定性计算(画像/分层)永远优先于模型;模型输出失败时降级为模板,不影响链路。

## 1. 健康检查

```
GET /healthz
→ 200 {"ok": true, "service": "agent-service", "db": "...", "llm": false}
```

## 2. 运营助手 — 三备选出稿(核心)

家长消息到达后数秒内返回三个定位不同的备选,逐条带质检结果。

```
POST /api/v1/drafts
{
  "uid": "1405777",            // 客户 ID(必填,须在库)
  "message": "班型多少钱?",      // 家长消息(必填)
  "cid": "C...",               // 可选,续会话传;首次不传,返回新 cid
  "recent_messages": ["..."]   // 可选,近 3 日历史消息(供意向识别)
}

→ 200
{
  "cid": "Cxxxx",
  "drafts": [
    {"id": "DR...", "variant": "A", "position": "标准口径", "text": "...",
     "qc": {"status": "green", "risks": [], "suggestion": null}},
    {"id": "DR...", "variant": "B", "position": "推进型",   "text": "...",
     "qc": {"status": "yellow", "risks": [{"type": "价格与优惠承诺", "level": "yellow",
            "matched": "锁价", "suggestion": "核对当期活动…"}], "suggestion": "..."}},
    {"id": "DR...", "variant": "C", "position": "关系型",   "text": "...", "qc": {...}}
  ],
  "customer_snapshot": {
    "uid": "1405777", "nickname": "嘉嘉", "tier": "S2",
    "summary": "近 7 日活跃 …", "activity": "中", "intent": "高"
  },
  "sop_hint": "price"            // 建议推进到的 SOP 阶段,可空
}
→ 404 {"error": "customer xxx not found"}
```

## 3. 发送闸门 + 留痕

老师选定/改写后点击发送时调用。**红线:红稿 409,Web 端置灰发送按钮。**

```
POST /api/v1/send
{
  "cid": "Cxxxx",
  "text": "最终发出的文本",       // 改写后的实际文本
  "variant": "A" | "B" | "C" | "CUSTOM",
  "edited": true,                // 是否改写过备选
  "confirmed": true,             // 黄色状态勾选「我已确认」
  "sender": "李老师"              // 发送人工号/姓名,留痕用
}

→ 200 {"ok": true, "gate": {
    "message_id": "MSG...", "variant": "B", "edited": true, "confirmed": true,
    "sender": "李老师", "qc_status": "green", "qc_risks": [], "sendable": true}}
→ 409 {"error": "质检未通过,禁止发送", "qc_status": "red", "risks": [...], "gate": {...}}
```

## 4. 独立质检(自定义回复同样过检)

```
POST /api/v1/qc {"text": "可以随时退款", "confirmed": false}
→ 200 {"status": "red", "risks": [{"type": "退费承诺", "level": "red",
       "matched": "随时退", "suggestion": "退费以您签署的课程服务协议为准…"}],
       "suggestion": "...", "sendable": false}
```

三态语义:`green` 直接可发 / `yellow` 需勾选确认(`confirmed: true`)才 `sendable` / `red` 永远不可发。

## 5. 用户画像(五块内容)

```
GET /api/v1/profile/{uid}
→ 200 {
  "uid": "...", "nickname": "嘉嘉",
  "activity": {"level": "高", "active_days": 6, "avg_minutes": 23.0,
               "evidence": "近7日活跃 6 天 / 日均阅读 23.0 分钟(阈值 ≥5 天 且 ≥15 分钟)"},
  "intent":  {"level": "高", "signals": ["问价", "约试听"],
              "evidence": "近3日推进信号 2 项:问价、约试听", "confidence": "high"},
  "segment": {"tier": "S1", "name": "S1 高价值推进"},
  "tier": "S1",
  "summary": "三句话行为概括",
  "tags_ai": ["高活跃度用户（…）", "高意向（…）"],   // 只读,带来源
  "tags_manual": ["高意向", "多次使用"],              // 人工标签,Web 端可增删
  "sop": {"stage": "课程与价格", "stayed_hours": 6.0, "status": "正常",
          "timeout": false, "suggest": "发送班型对比与当期政策"},
  "phone_masked": "133****8666"
}
```

判定硬规则(可在界面展示依据):活跃度=近 7 日 ≥5 天且日均 ≥15 分钟;意向度=近 3 日推进信号 2 项;分层 S1/S2/S3 组合。

## 6. 增值分析师 — 今日跟进名单

```
GET /api/v1/growth/daily?limit=50[&uid=1405777]
→ 200 {
  "date": "2026-11-08", "total_customers": 157444, "sampled": 50,
  "segments": [
    {"tier": "S1", "name": "S1 高价值推进", "count": 3, "action": "…",
     "script": "专属话术…", "customers": [{uid, nickname, activity, intent, evidence, summary}]},
    …S2、S3
  ], "note": "…置信度说明"
}
```

- `limit`:扫描面取 `max(limit*50, 5000)`,返回每层最多 10 条示例(全量可分页)
- `uid`:只查单个客户(协作闭环验证用),返回其所在分层与最新依据
- 意向信号来源:对话消息(含运营助手会话留痕,回流计入)+ 行为代理(链接点击/意向标签/测字,置信度标 `low`)

```
GET /api/v1/growth/report   → 分层分布(工作台用)
```

## 7. SOP 看板与人工调整

```
GET /api/v1/sop/board?limit=20[&uid=]
→ 200 {"board": [{"uid", "nickname", "stage", "stayed_hours", "status": "正常|超时|已停止",
                  "timeout": true, "suggest": "…"}]}

POST /api/v1/sop/change
{"field": "stay_limit_hours", "old_value": "24", "new_value": "48",
 "scope": "once|default|log_only", "reason": "客户决策周期长", "editor": "李老师"}
→ 200 {"ok": true, "change": {...}}     // 三种生效范围 + 变更留痕,支持回滚
```

## 8. 客户检索与会话回放

```
GET /api/v1/customers?search=&signup=两年&tag_like=高意向&limit=20&offset=0
→ 200 {"total": 123, "items": [...]}    // 不含手机号与逐日阅读明细

GET /api/v1/messages/{cid}
→ 200 {"cid": "...", "messages": [{id, role: parent|teacher, text, created_at,
       sender, variant, edited, confirmed, qc_status, qc_risks}]}   // 全程留痕可回放
```

## 9. 错误约定

| 状态码 | 含义 |
|---|---|
| 200 | 成功 |
| 204 | OPTIONS 预检 |
| 404 | 资源不存在(`{"error": "..."}`) |
| 409 | 质检红灯拒绝发送 |
| 500 | 服务内部错误(`{"error": "..."}`) |

## 10. 本地联调

```bash
# 1) 数据(一次性,Excel → SQLite;接 MySQL 后换 adapter)
python3 -I scripts/import_excel.py

# 2) 启动服务(默认 127.0.0.1:8080;LLM 关,走确定性模板)
python3 -I -m service.app
#    联调 MiMo 生成:OPC_SERVICE_LLM=on python3 -I -m service.app

# 3) 测试
python3 -I -m unittest discover -s tests
```

数据访问层:`service/repository.py` 定义 `Repository` 抽象,现在是 `SQLiteRepository`(Excel 导入);Database 同学交付 MySQL 后新增 `MySQLRepository` 实现同一接口即可,业务代码零改动。
