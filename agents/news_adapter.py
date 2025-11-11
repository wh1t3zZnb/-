from typing import List, Dict
from urllib.parse import urlparse
from datetime import datetime, timedelta


def _lazy_feedparser():
    try:
        import feedparser  # type: ignore
        return feedparser
    except Exception:
        return None


def _domain_of(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


def _cutoff_for_timelimit_ui(timelimit_ui: str) -> datetime:
    now = datetime.now()
    if timelimit_ui == "w":
        return now - timedelta(days=7)
    if timelimit_ui == "m":
        return now - timedelta(days=30)
    if timelimit_ui == "90":
        return now - timedelta(days=90)
    # 默认：一年
    return now - timedelta(days=365)


def search_rss(query: str, feeds: List[str], max_results: int, timelimit_ui: str) -> List[Dict]:
    """
    从 RSS 源拉取新闻条目并按主题过滤，返回统一结构：title/href/body/source。
    注意：若 feedparser 缺失或 feeds 为空，返回空列表。
    """
    fp = _lazy_feedparser()
    if not fp or not feeds:
        return []

    cutoff = _cutoff_for_timelimit_ui(timelimit_ui)
    keywords = [k for k in (query or "").split() if k]

    results: List[Dict] = []
    for url in feeds:
        try:
            feed = fp.parse(url)
        except Exception:
            continue
        for entry in feed.get("entries", []):
            title = entry.get("title", "")
            href = entry.get("link", "")
            summary = entry.get("summary", "") or entry.get("description", "") or ""

            # 时间过滤（published/updated）
            dt = None
            for key in ("published_parsed", "updated_parsed"):
                t = entry.get(key)
                if t:
                    try:
                        dt = datetime(*t[:6])
                        break
                    except Exception:
                        pass
            if dt and dt < cutoff:
                continue

            # 关键词匹配（朴素）：至少命中一个关键词
            text = f"{title} {summary}"
            if keywords and not any(k in text for k in keywords):
                continue

            results.append({
                "title": title,
                "href": href,
                "body": summary,
                "source": _domain_of(href) or (feed.get("feed", {}).get("title") or "RSS")
            })
            if len(results) >= max_results:
                break

    return results