"""
LLM 检索策略规划（Query Planner）
- 入口：plan_query(query, config)
- 行为：
  1) 若检测到可用的 LLM API（如 OpenAI），则调用模型生成检索策略（国内优先、时间窗、关键词、最大条数等）。
  2) 若无可用 LLM 或调用失败，则回退到规则版：
     - 国内优先（domestic_only=True），优先使用 Baidu 与国内 RSS。
     - 关键词：拆分空格，附加常见方面词（如 “最新” “舆情” “争议” “评价”）。
     - 时间窗：近30天（m）。
     - 配额：20。
"""

from typing import Dict, List
import os
from .llm_client_volc import build_volc_from_config


def _rule_fallback(query: str) -> Dict:
    kws = [k for k in query.split() if k]
    # 常见方面词，帮助覆盖更多相关文本
    aspect_words = ["最新", "舆情", "争议", "评价", "事件", "新闻"]
    keywords = list(dict.fromkeys(kws + aspect_words))  # 去重保序
    return {
        "keywords": keywords,
        "timelimit": "m",  # 近30天
        "max_results": 20,
        "domestic_only": True,
        "use_duckduckgo": False,
        "use_baidu": True,
        "use_rss": True,
    }


def plan_query(query: str, config: Dict) -> Dict:
    # 优先使用 Volc Ark
    volc = build_volc_from_config(config)
    if volc:
        try:
            prompt = (
                "你是检索策略规划助手。根据用户的问题，输出一个JSON，字段包括："
                "keywords(数组)、timelimit(取w/m/90之一)、max_results(数字)、"
                "domestic_only(True/False)、use_duckduckgo(True/False)、use_baidu(True/False)、use_rss(True/False)。"
                "默认国内优先，并限制每次迭代抓取条数为5。问题：" + query
            )
            text = volc.chat(
                messages=[{"role": "system", "content": "你是检索策略规划助手。"}, {"role": "user", "content": prompt}],
                temperature=0.2,
            )
            import json

            plan = json.loads(text)
            # 规范化与缺省
            plan.setdefault("timelimit", "m")
            plan.setdefault("max_results", 20)
            plan.setdefault("domestic_only", True)
            plan.setdefault("use_duckduckgo", False)
            plan.setdefault("use_baidu", True)
            plan.setdefault("use_rss", True)
            ks = plan.get("keywords") or []
            plan["keywords"] = [k for k in ks if isinstance(k, str) and k.strip()]
            return plan
        except Exception:
            pass
    # 回退规则
    return _rule_fallback(query)