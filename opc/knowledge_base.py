"""知识库读取与轻量检索(Context Hub 的检索面)。"""
import json
import os
import re

from . import config


def _load(name: str):
    path = os.path.join(config.KNOWLEDGE_DIR, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def qc_rules() -> dict:
    return _load("qc_rules.json") or {}


def qa_items() -> list:
    return _load("qa.json") or []


def sop_days() -> dict:
    return _load("sop.json") or {}


def chats() -> dict:
    return _load("chats.json") or {}


def _bigrams(text: str) -> set:
    t = re.sub(r"[^一-鿿A-Za-z0-9]", "", text)
    return {t[i:i + 2] for i in range(len(t) - 1)} if len(t) > 1 else {t}


def search_qa(question: str, top: int = 2) -> list:
    """按字符二元组重合度检索最相关的家长异议应答。"""
    items = qa_items()
    q = _bigrams(question)
    scored = []
    for it in items:
        bg = _bigrams(it["question"] + " " + it["answer"][:100])
        score = len(q & bg) / max(len(q), 1)
        scored.append((score, it))
    scored.sort(key=lambda x: -x[0])
    return [it for s, it in scored[:top] if s > 0.05]


def search_sop(keyword: str = "", day: str | None = None) -> dict:
    """取指定营期日的 SOP;无 day 时按关键词找相关条目。

    day 兼容多种写法:D4 / Day4 / 运营期-D4 → 匹配「运营期-Day4」。
    """
    days = sop_days()
    if day:
        norm = lambda s: s.upper().replace(" ", "").replace("DAY", "D")  # noqa: E731
        matches = {k: v for k, v in days.items() if norm(day) in norm(k)}
        if len(matches) > 1:  # D1 同时命中承接期/运营期时优先运营期
            for k in matches:
                if "运营" in k:
                    return {k: matches[k]}
        return dict(list(matches.items())[:1])
    hits = {}
    for k, entries in days.items():
        matched = [e for e in entries
                   if keyword and keyword in json.dumps(e, ensure_ascii=False)]
        if matched:
            hits[k] = matched
    return hits
