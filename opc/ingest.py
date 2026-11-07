"""素材摄取:把主办方/客户真实素材吃进 Context Hub 与知识库。

- sop - 检索.xlsx   → knowledge/sop.json      (逐日运营 SOP)
- 用户问题.docx     → knowledge/qa.json       (家长异议应答手册)
- 禁止词.docx       → knowledge/qc_rules.json (质检细则,已人工结构化,原图留档)
- D****_群聊消息.xlsx → knowledge/chats.json   (真实家长群语料)
"""
import json
import os
import re
import zipfile

from . import config
from .llm import log_action


def ingest(material_dir: str | None = None) -> dict:
    mdir = material_dir or config.MATERIAL_DIR
    stats = {}

    stats["sop"] = _ingest_sop(mdir)
    stats["qa"] = _ingest_qa(mdir)
    stats["chats"] = _ingest_chats(mdir)
    stats["qc_rules"] = _check_qc_rules(mdir)

    _write_hub(stats)
    log_action("摄取员", f"素材目录 {mdir}", f"完成摄取:{stats}", status="OK")
    return stats


# ---------- SOP ----------

def _ingest_sop(mdir: str) -> int:
    import openpyxl

    path = os.path.join(mdir, "sop - 检索.xlsx")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    days = {}
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        day_label = str(rows[0][0] or ws.title).strip()
        entries = []
        current = None
        header_seen = False
        for row in rows[1:]:
            cells = [str(c).strip() if c is not None else "" for c in row]
            if not any(cells):
                continue
            if not header_seen and cells[0] == "执行时间":
                header_seen = True
                continue
            if cells[0] and cells[0] not in ("", "执行时间"):
                current = {
                    "time": cells[0], "scene": cells[1] if len(cells) > 1 else "",
                    "target": cells[2] if len(cells) > 2 else "",
                    "scripts": [], "materials": [], "note": "",
                }
                entries.append(current)
            if current is None:
                continue
            script = cells[3] if len(cells) > 3 else ""
            mats = [c for c in cells[4:7] if c] if len(cells) > 4 else []
            note = cells[7] if len(cells) > 7 else ""
            if script:
                current["scripts"].append(script)
            current["materials"].extend(mats)
            if note:
                current["note"] = (current["note"] + " " + note).strip()
        days[day_label] = entries
    wb.close()

    _save("sop.json", days)
    return sum(len(v) for v in days.values())


# ---------- 用户问题 QA ----------

def _ingest_qa(mdir: str) -> int:
    import docx

    d = docx.Document(os.path.join(mdir, "用户问题.docx"))
    qa = []
    cur = None
    for p in d.paragraphs:
        t = p.text.strip()
        if not t:
            continue
        m = re.match(r"^(Q\d+)[、.]\s*(.+)", t)
        if m:
            cur = {"id": m.group(1), "question": m.group(2).strip(), "answer": []}
            qa.append(cur)
        elif cur is not None:
            cur["answer"].append(t)
    for item in qa:
        item["answer"] = "\n".join(item["answer"])

    _save("qa.json", qa)
    return len(qa)


# ---------- 群聊消息 ----------

def _ingest_chats(mdir: str) -> int:
    import openpyxl

    total = 0
    chats = {}
    for fname in sorted(os.listdir(mdir)):
        if not fname.endswith("_群聊消息.xlsx"):
            continue
        wb = openpyxl.load_workbook(os.path.join(mdir, fname), read_only=True, data_only=True)
        msgs = []
        for ws in wb.worksheets:
            for row in ws.iter_rows(min_row=2, values_only=True):
                cells = [str(c) if c is not None else "" for c in row]
                if not any(cells) or cells[0].startswith("==="):
                    continue
                if len(cells) < 6:
                    continue
                msgs.append({
                    "group": cells[0], "id": cells[1], "time": cells[2],
                    "sender": cells[3], "type": cells[4], "content": cells[5],
                })
        wb.close()
        chats[fname.replace("_群聊消息.xlsx", "")] = msgs
        total += len(msgs)

    _save("chats.json", chats)
    return total


# ---------- 质检细则 ----------

def _check_qc_rules(mdir: str) -> str:
    """qc_rules.json 已人工结构化;这里把原始图片留档,保证可追溯。"""
    rules_path = os.path.join(config.KNOWLEDGE_DIR, "qc_rules.json")
    if not os.path.exists(rules_path):
        raise FileNotFoundError("缺少 knowledge/qc_rules.json(质检细则)")
    src = os.path.join(mdir, "禁止词.docx")
    media_dir = os.path.join(config.KNOWLEDGE_DIR, "qc_rules_images")
    os.makedirs(media_dir, exist_ok=True)
    with zipfile.ZipFile(src) as z:
        for name in z.namelist():
            if name.startswith("word/media/"):
                target = os.path.join(media_dir, os.path.basename(name))
                if not os.path.exists(target):
                    with open(target, "wb") as f:
                        f.write(z.read(name))
    return "ok"


# ---------- Context Hub ----------

def _write_hub(stats: dict) -> None:
    sop = _load("sop.json")
    qa = _load("qa.json")
    days = list(sop.keys())
    _write("01-market.md", f"""# 01 · 市场与客户档案

> 由摄取员从真实素材自动建档

## 首个客户:适趣AI中文(儿童中文阅读识字产品)

- 产品形态:App 阅读识字 + 21 天阅读训练营(社群运营)+ 长期会员(2 年)
- 转化路径:训练营免费/低价体验 → 期中续费团购 → 期满转化长期会员(约 3098 元)
- 训练营节奏:{' / '.join(days)}
- 目标人群:3–8 岁孩子家长(妈妈为主)
- 真实语料:3 个家长群共 {stats.get('chats', 0)} 条消息;家长异议手册 {stats.get('qa', 0)} 条

## 竞品与替代

- 识字类 App(洪恩识字、悟空识字等)、线下绘本馆、家长自鸡
- 差异点:AI 千人千面测识字量 + 动态推荐绘本 + 伴学老师服务
""")
    _write("02-brand.md", f"""# 02 · 品牌与语调

- 产品名:**适趣AI中文**(旧名「适趣AI阅读」已弃用,对外不得再用)
- 伴学老师人设:亲切、专业、有温度;称呼「xx妈妈/爸爸」;适度 emoji
- 禁词与敏感词:见 `knowledge/qc_rules.json`(课程→阅读会员、学习→阅读、试用→21天APP使用权限 等)
- 红线:不刷单、不虚假承诺、不承诺「百分百有效/绝对认识 xx 字/随时退款」
""")
    _write("03-product.md", f"""# 03 · 服务产品包(我司对外售卖)

**服务**:AI 社群代运营 —— 训练营社群全周期操盘(SOP 落地 + 家长异议应答 + 续费转化 + 质检合规)

交付物:每日运营包(私聊/社群/朋友圈三线话术)、家长应答工单、质检报告、经营周报。

内部系统:MiMo Agent 团队(COO 总编排 + 专职 Agent + 9 道人工闸门 + 全量留痕)。
""")
    _write("04-ops.md", f"""# 04 · 运营 SOP 与质检

- SOP 台账:`knowledge/sop.json`({stats.get('sop', 0)} 条执行动作,覆盖 {' / '.join(days[:6])} …)
- 异议应答:`knowledge/qa.json`({stats.get('qa', 0)} 条)
- 质检细则:`knowledge/qc_rules.json`(敏感词/绝对词/过度承诺/退费规范/响应时限 30 分钟)
- 权限表:API 密钥仅存环境变量,不入对话正文;对外发布/收款/退款均过人工闸门
""")


def _save(name: str, data) -> None:
    with open(os.path.join(config.KNOWLEDGE_DIR, name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)


def _load(name: str):
    with open(os.path.join(config.KNOWLEDGE_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def _write(name: str, text: str) -> None:
    with open(os.path.join(config.HUB_DIR, name), "w", encoding="utf-8") as f:
        f.write(text)
