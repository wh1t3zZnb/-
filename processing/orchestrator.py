"""
迭代编排（Orchestrator 1.0）
按用户要求：
1) LLM 判断怎么搜（每次5条），生成策略。
2) 按策略搜索（国内优先：Baidu+RSS）。
3) 整合信息，先用摘要让 LLM 判断是否符合需求，进行清洗（保留相关）。
4) 若符合，再抓取详细正文并汇总，LLM再次判断是否满足；若不满足，继续下一轮再搜5条，直到满足或达到最大迭代。
"""

from typing import Dict, List, Tuple
from ..agents.llm_planner import plan_query
from ..agents.baidu_adapter import search_baidu
from ..agents.news_adapter import search_rss
from .cleaning import dedup_by_href, filter_chinese
from .fetcher import enrich_items_with_content
from ..agents.llm_client_volc import build_volc_from_config


def _build_item_summary(it: Dict) -> str:
    title = it.get("title", "")
    body = it.get("body", "")
    return (title + "\n" + body).strip()


def _llm_filter_items(query: str, items: List[Dict], cfg: Dict) -> Tuple[List[Dict], List[Dict]]:
    """让 LLM 根据摘要筛选相关项。返回 (accepted, rejected)。"""
    llm = build_volc_from_config(cfg)
    if not llm:
        # 无 LLM 时，简单规则：保留包含关键字的项
        kws = [k for k in query.split() if k]
        acc = [it for it in items if any(k in (it.get("title", "") + it.get("body", "")) for k in kws)]
        rej = [it for it in items if it not in acc]
        return acc, rej

    # 将多个摘要拼接为一个列表，让模型输出每条的 yes/no
    lines = []
    for idx, it in enumerate(items, 1):
        lines.append(f"[{idx}]\n" + _build_item_summary(it))
    prompt = (
        "用户问题：" + query + "\n" +
        "下面是候选摘要列表，请针对每条回答 yes 或 no，表示是否与用户需求高度相关。"
        "只输出一个 JSON 数组，如 [true,false,...]，长度与候选条数一致。\n\n" +
        "候选：\n" + "\n\n".join(lines)
    )
    out = llm.chat(messages=[{"role": "system", "content": "你是相关性筛选助手。"}, {"role": "user", "content": prompt}], temperature=0)
    import json
    try:
        flags = json.loads(out)
        accepted = []
        rejected = []
        for it, f in zip(items, flags):
            if bool(f):
                accepted.append(it)
            else:
                rejected.append(it)
        return accepted, rejected
    except Exception:
        # 解析失败时，保守地全保留
        return items, []


def _llm_judge_full_text(query: str, items: List[Dict], cfg: Dict) -> Tuple[bool, str]:
    """用 LLM 根据抓取的全文进行综合判断与汇总。返回 (满足需求?, 综合摘要)。"""
    llm = build_volc_from_config(cfg)
    # 汇总文本
    texts = []
    for it in items:
        txt = it.get("content") or _build_item_summary(it)
        if txt:
            texts.append(f"- {it.get('title','')}\n{txt}")
    joined = "\n\n".join(texts[:5])  # 控制长度
    if llm:
        prompt = (
            "用户问题：" + query + "\n\n" +
            "请阅读以下材料，输出一个 JSON：{\"satisfy\": true/false, \"summary\": \"综合结论与要点\"}.\n" +
            "材料：\n" + joined
        )
        out = llm.chat(messages=[{"role": "system", "content": "你是总结与判定助手。"}, {"role": "user", "content": prompt}], temperature=0.2)
        import json
        try:
            data = json.loads(out)
            return bool(data.get("satisfy")), str(data.get("summary", ""))
        except Exception:
            pass
    # 无 LLM 或解析失败，规则版：如果有3条以上内容则认为可输出
    ok = len(items) >= 3
    summary = f"基于{len(items)}条材料的规则版汇总：请人工复核。"
    return ok, summary


def run_iterative_flow(query: str, CONFIG: Dict) -> Tuple[List[Dict], str, Dict]:
    plan = plan_query(query, CONFIG)
    iter_size = int(CONFIG.get("loop", {}).get("iter_size", 5))
    max_iter = int(CONFIG.get("loop", {}).get("max_iterations", 4))
    domestic_only = bool(plan.get("domestic_only", True))
    use_rss = bool(plan.get("use_rss", True))
    feeds = CONFIG["search"].get("news_feeds", [])

    all_items: List[Dict] = []
    accepted_all: List[Dict] = []
    debug = {"iterations": 0, "accepted": 0, "filtered": 0}

    for i in range(max_iter):
        debug["iterations"] = i + 1
        # 2) 搜索（国内优先）
        batch: List[Dict] = []
        # Baidu
        batch.extend(search_baidu(query, max_results=iter_size) or [])
        # RSS（国内源）
        if use_rss and feeds:
            batch.extend(search_rss(query, feeds=feeds, max_results=iter_size, timelimit_ui="m") or [])
        # 清洗与去重
        batch = filter_chinese(batch, chinese_only=True)
        batch = dedup_by_href(batch)
        all_items.extend(batch)

        # 3) LLM 根据摘要筛选
        accepted, _ = _llm_filter_items(query, batch, CONFIG)
        debug["filtered"] += len(batch)
        accepted_all.extend(accepted)
        debug["accepted"] = len(accepted_all)

        # 4) 若有符合项，抓全文并综合判断
        if accepted_all:
            enrich_items_with_content(accepted_all, top_k=min(3, len(accepted_all)))
            ok, final_summary = _llm_judge_full_text(query, accepted_all, CONFIG)
            if ok:
                return accepted_all, final_summary, debug
        # 否则继续下一轮

    # 达到最大迭代仍不满足，输出当前已抓到的内容并给出保守总结
    if accepted_all:
        enrich_items_with_content(accepted_all, top_k=min(3, len(accepted_all)))
    final_summary = f"达到最大迭代({max_iter})仍未满足需求。返回当前{len(accepted_all)}条较相关材料的初步汇总，建议继续检索或调整问题。"
    return accepted_all or all_items, final_summary, debug