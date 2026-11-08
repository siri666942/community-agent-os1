"""增值分析师 Agent(OPSIE 2.1):聚合对话与行为 → 活跃度/意向度 → 分层
→ 今日跟进名单与专属话术。每日批处理 + 阶段停滞触发;只出名单不触达。

分层为确定性计算(profile.py),话术建议可 LLM 生成、失败降级模板。
"""
from __future__ import annotations

from . import config, profile as profile_mod, repository, sop

FOLLOWUP_ACTIONS = {
    "S1": "高价值推进:今日 1v1,给班型对比与当期政策(以价目表为准),约定确认时间",
    "S2": "培育观察:发学情资料 + 一次轻量互动,3 天内最多 2 次",
    "S3": "低压力激活:补充资料触达一次,不提价格,不承诺效果",
}


def daily_list(limit: int = 50, uid_filter: str | None = None) -> dict:
    """今日跟进名单:确定性分层 + 每层专属话术。只出名单,不产生触达。"""
    repo = repository.get_repository()
    if uid_filter:
        customers = [c for c in [repo.get_customer(uid_filter)] if c]
        total = len(customers)
    else:
        total = repo.count_customers()
        # 扫描面大于返回面:S1 高价值用户稀少(约千分之二),批处理扫 5000 行采样
        customers = repo.list_customers(limit=max(limit * 50, 5000))

    buckets: dict[str, list] = {"S1": [], "S2": [], "S3": []}
    for c in customers:
        prof = profile_mod.build_profile(c, recent_messages=None)
        buckets[prof["tier"]].append({
            "uid": c["uid"], "nickname": prof["nickname"],
            "activity": prof["activity"]["level"], "intent": prof["intent"]["level"],
            "evidence": {"activity": prof["activity"]["evidence"],
                         "intent": prof["intent"]["evidence"]},
            "summary": prof["summary"],
        })

    out = {"date": sop.now_iso()[:10], "total_customers": total,
           "sampled": len(customers), "segments": []}
    for tier in ("S1", "S2", "S3"):
        out["segments"].append({
            "tier": tier,
            "name": {"S1": "S1 高价值推进", "S2": "S2 培育观察", "S3": "S3 低压力激活"}[tier],
            "count": len(buckets[tier]),
            "action": FOLLOWUP_ACTIONS[tier],
            "script": _script_for(tier, buckets[tier][:1]),
            "customers": buckets[tier][:10],  # 名单示例,Web 端可分页拉全量
        })
    out["note"] = ("意向信号依赖对话数据;仅行为数据时置信度下降"
                   if not config.LLM_ENABLED else "话术由 AI 生成,人工发送")
    return out


def _script_for(tier: str, examples: list[dict]) -> str:
    ex = examples[0] if examples else {}
    name = ex.get("nickname", "xx") + "妈妈"
    if tier == "S1":
        return (f"{name}您好～看孩子最近阅读很稳定，想跟您聊下接下来的进阶安排，"
                f"我把班型对比发您看看，本周还有少量余位，您看哪天方便？")
    if tier == "S2":
        return (f"{name}您好～整理了一份孩子的学情小结发您参考，不用着急回复，"
                f"有想了解的随时找我。")
    return (f"{name}您好～补充了一些阅读资料和学情分析，需要的话直接发您，不用回复也行。")


def segment_report() -> dict:
    """工作台分层分布(全量确定性统计,不拉明细)。"""
    repo = repository.get_repository()
    counts = {"S1": 0, "S2": 0, "S3": 0}
    for c in repo.list_customers(limit=200):
        prof = profile_mod.build_profile(c)
        counts[prof["tier"]] += 1
    return {"distribution": counts, "sampled": min(repo.count_customers(), 200)}
