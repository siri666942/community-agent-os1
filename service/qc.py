"""话术质检:规则引擎先于模型判断(OPSIE 七)。

三态:绿 通过 / 黄 提示(勾选确认后可发)/ 红 拦截(发送置灰)。
敏感六类:退费承诺(拦截)、提分升学承诺(拦截)、师资资质夸大(提示)、
价格优惠承诺(提示)、竞品贬低(提示)、学生隐私(拦截)。
"""
from __future__ import annotations

import re

# ── 规则表:每条 = (命中正则, 风险类型, 级别, 合规改写建议) ──────────
# level: red = 拦截 / yellow = 提示
RULES: list[tuple[re.Pattern, str, str, str]] = [
    # 退费承诺 → 拦截
    (re.compile(r"随时退|无条件.{0,6}退|全额退|不满意.{0,6}退|承诺.{0,4}退|想退就退"),
     "退费承诺", "red",
     "退费以您签署的课程服务协议为准，我先把正式退费规则发给您确认。"),
    # 提分与升学承诺 → 拦截(禁止词直接锁发送)
    (re.compile(r"保证提分|保提分|保过|一定进重点班|百分百|提分保证|保证.{0,4}分|必过|包过"),
     "提分升学承诺", "red",
     "改为说明课程内容与学习安排，效果表述用「逐步积累」「因人而异」，不承诺幅度与时间。"),
    # 学生隐私 → 拦截(群里提成绩/姓名/家庭情况)
    (re.compile(r"成绩单|家庭住址|家庭情况|身份证|真实姓名|全名是|排名情况"),
     "学生隐私", "red",
     "涉及学生个人信息请转私聊，并先确认家长授权后再沟通。"),
    # 师资资质夸大 → 提示
    (re.compile(r"全部.{0,6}(重点校|在职|名师)|名师.{0,4}(全部|都)在职|一线名师|名师保证"),
     "师资资质夸大", "yellow",
     "改为引用官方师资介绍原文，不做整体性资质断言。"),
    # 价格与优惠承诺 → 提示(需核对当期活动并勾选确认)
    (re.compile(r"今天最低价|给你锁价|锁价|最后.{0,4}价|最低价|保证.{0,4}优惠|优惠.{0,4}(锁定|保留)"),
     "价格与优惠承诺", "yellow",
     "标注「优惠需核对当期活动」「价格以价目表为准」，核对后再发。"),
    # 竞品贬低 → 提示
    (re.compile(r"比.{0,8}(机构|家|品牌).{0,6}(强|好)多了|吊打|碾压|别家都不行|其他机构都不行"),
     "竞品贬低", "yellow",
     "改为客观差异说明，不评价他机构。"),
    # 旧产品名 → 提示(品牌口径)
    (re.compile(r"适趣AI阅读"),
     "品牌口径", "yellow", "统一使用「适趣AI中文」。"),
]

# 量效数字承诺:出现「N天认识N字」类效果数字 → 提示(可争论阈值,先拦提示)
EFFECT_NUMBER = re.compile(r"\d+\s*天.{0,8}(认识|学会|掌握)\s*\d+|识字量.{0,4}\d{3,4}|达到\s*\d{3,4}\s*(个字|字)")
SELF_CORRECTION = re.compile(r"哦不对|应该是|更正一下|抱歉.{0,4}(重|改)|\(哦|（哦")


def check(text: str) -> dict:
    """文本质检 → {"status": "green|yellow|red", "risks": [...], "suggestion": str|None}。"""
    risks = []
    for pattern, rtype, level, advice in RULES:
        m = pattern.search(text)
        if m:
            risks.append({"type": rtype, "level": level,
                          "matched": m.group(0), "suggestion": advice})
    m = EFFECT_NUMBER.search(text)
    if m and not any(r["type"] == "提分升学承诺" for r in risks):
        risks.append({"type": "量效数字承诺", "level": "yellow",
                      "matched": m.group(0),
                      "suggestion": "效果数字改为区间或定性表述，注明个体差异。"})
    m = SELF_CORRECTION.search(text)
    if m:
        risks.append({"type": "自我修正语", "level": "yellow", "matched": m.group(0),
                      "suggestion": "删除改口痕迹，直接给出最终表述。"})

    if any(r["level"] == "red" for r in risks):
        status = "red"
    elif risks:
        status = "yellow"
    else:
        status = "green"
    suggestion = next((r["suggestion"] for r in risks if r["level"] == "red"),
                      risks[0]["suggestion"] if risks else None)
    return {"status": status, "risks": risks, "suggestion": suggestion}


def is_sendable(status: str, confirmed: bool = False) -> bool:
    """发送闸门:红锁死;黄需勾选「我已确认」;绿直接可发。"""
    if status == "red":
        return False
    if status == "yellow":
        return bool(confirmed)
    return True
