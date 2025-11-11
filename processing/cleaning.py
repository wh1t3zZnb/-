import re
from typing import List, Dict
from urllib.parse import urlparse


CN_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


def filter_chinese(items: List[Dict], chinese_only: bool = True) -> List[Dict]:
    if not chinese_only:
        return items
    filtered = []
    for it in items:
        text = (it.get("title", "") or "") + " " + (it.get("body", "") or "")
        if CN_CHAR_RE.search(text):
            filtered.append(it)
    return filtered


def dedup_by_href(items: List[Dict]) -> List[Dict]:
    seen = set()
    uniq = []
    for it in items:
        href = it.get("href")
        if not href:
            # 无链接的结果意义较小，略过
            continue
        if href in seen:
            continue
        seen.add(href)
        uniq.append(it)
    return uniq


def simple_relevance_score(item: Dict, keywords: List[str]) -> float:
    title = item.get("title", "") or ""
    body = item.get("body", "") or ""
    text = f"{title} {body}"
    k_hits = sum(text.count(k) for k in keywords if k)
    # 朴素打分：关键词命中次数为主
    return float(k_hits)


def sort_by_relevance(items: List[Dict], keywords: List[str]) -> List[Dict]:
    return sorted(items, key=lambda it: simple_relevance_score(it, keywords), reverse=True)


def filter_by_domain(items: List[Dict], whitelist: List[str], blacklist: List[str]) -> List[Dict]:
    """根据域名白/黑名单过滤结果。
    - whitelist 非空时，仅保留域名后缀匹配的条目（例如 'weibo.com'、'news.sina.com.cn'）。
    - blacklist 非空时，剔除域名后缀匹配的条目。
    两者同时存在时，先应用 whitelist，再应用 blacklist。
    """
    def domain_of(href: str) -> str:
        try:
            return urlparse(href).netloc.lower()
        except Exception:
            return ""

    def matches_any(domain: str, patterns: List[str]) -> bool:
        domain = domain or ""
        for p in patterns or []:
            p = p.lower().strip()
            if not p:
                continue
            # 后缀匹配（子域也算匹配）
            if domain == p or domain.endswith("." + p):
                return True
        return False

    filtered = items
    if whitelist:
        filtered = [it for it in filtered if matches_any(domain_of(it.get("href", "")), whitelist)]
    if blacklist:
        filtered = [it for it in filtered if not matches_any(domain_of(it.get("href", "")), blacklist)]
    return filtered