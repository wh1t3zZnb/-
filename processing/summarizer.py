from typing import List, Dict, Tuple


POS_WORDS = {"好", "赞", "支持", "认可", "优秀", "经典", "佳"}
NEG_WORDS = {"差", "骂", "争议", "批评", "失望", "不好", "负面"}


def sentiment_counts(items: List[Dict]) -> Tuple[int, int, int]:
    pos = 0
    neg = 0
    neu = 0
    for it in items:
        # 优先使用抓取的全文内容，其次 body，最后 title
        text = it.get("content") or f"{it.get('title', '')} {it.get('body', '')}"
        hits_pos = sum(1 for w in POS_WORDS if w in text)
        hits_neg = sum(1 for w in NEG_WORDS if w in text)
        if hits_pos > hits_neg and hits_pos > 0:
            pos += 1
        elif hits_neg > hits_pos and hits_neg > 0:
            neg += 1
        else:
            neu += 1
    return pos, neg, neu


def build_summary(items: List[Dict], query: str) -> str:
    if not items:
        return (
            f"围绕‘{query}’的公开文本检索，未检索到有效中文结果或结果被过滤。"
            f"请尝试：调整关键词、扩大时间窗、减少白名单限制或检查网络/依赖（duckduckgo-search）。"
        )
    pos, neg, neu = sentiment_counts(items)
    total = len(items)
    return (
        f"围绕‘{query}’的公开文本讨论，初步显示："
        f"正面样本约{pos}/{total}，负面样本约{neg}/{total}，中性/不明显约{neu}/{total}。"
        f"该结论为MVP规则初判，建议后续补充平台覆盖与评论层抓取以提高稳健性。"
    )