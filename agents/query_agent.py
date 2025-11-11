from typing import List, Dict
from urllib.parse import urlparse


def search_web(query: str, max_results: int = 30, timelimit: str = "m") -> List[Dict]:
    """
    使用 DuckDuckGo 进行文本检索。
    - query: 查询关键词（中文优先）
    - max_results: 最大返回条数
    - timelimit: 时间限制，如 'd'（天）、'w'（周）、'm'（月）、'y'（年）
    返回统一结构：title, href, body, source
    """
    results = []
    try:
        # 优先使用新包名 ddgs（更稳定），兼容旧包 duckduckgo_search
        try:
            from ddgs import DDGS  # type: ignore
        except Exception:
            from duckduckgo_search import DDGS  # type: ignore
        with DDGS() as ddgs:
            # 优先中文区域
            for r in ddgs.text(query, max_results=max_results, timelimit=timelimit, region="cn-zh"):
                href = r.get("href", "")
                try:
                    domain = urlparse(href).netloc.lower()
                except Exception:
                    domain = ""
                results.append({
                    "title": r.get("title", ""),
                    "href": href,
                    "body": r.get("body", ""),
                    "source": domain or "duckduckgo",
                })
            # 次选全球区域
            if not results:
                for r in ddgs.text(query, max_results=max_results, timelimit=timelimit, region="wt-wt"):
                    href = r.get("href", "")
                    try:
                        domain = urlparse(href).netloc.lower()
                    except Exception:
                        domain = ""
                    results.append({
                        "title": r.get("title", ""),
                        "href": href,
                        "body": r.get("body", ""),
                        "source": domain or "duckduckgo",
                    })
            # 兜底：新闻检索（中文区域）
            if not results:
                for r in ddgs.news(query, max_results=max_results, timelimit=timelimit, region="cn-zh"):
                    href = r.get("url", "")
                    try:
                        domain = urlparse(href).netloc.lower()
                    except Exception:
                        domain = ""
                    results.append({
                        "title": r.get("title", ""),
                        "href": href,
                        "body": r.get("body", "") or r.get("excerpt", ""),
                        "source": domain or "duckduckgo",
                    })
            # 最后兜底：新闻检索（全球区域，不设 timelimit）
            if not results:
                for r in ddgs.news(query, max_results=max_results, region="wt-wt"):
                    href = r.get("url", "")
                    try:
                        domain = urlparse(href).netloc.lower()
                    except Exception:
                        domain = ""
                    results.append({
                        "title": r.get("title", ""),
                        "href": href,
                        "body": r.get("body", "") or r.get("excerpt", ""),
                        "source": domain or "duckduckgo",
                    })
    except Exception:
        # 留空列表，前端提示依赖未安装或网络不可用
        return []
    return results