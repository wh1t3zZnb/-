from typing import List, Dict
from urllib.parse import quote, urlparse
import re


def _fetch_html(url: str) -> str:
    try:
        import requests  # type: ignore
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return resp.text
    except Exception:
        return ""
    return ""


def search_baidu(query: str, max_results: int = 30) -> List[Dict]:
    """
    朴素的百度网页检索解析（无动态渲染）：
    - 返回结构：title, href, body, source
    - 解析规则：<h3> 区域的链接标题与相邻摘要
    注意：此适配器仅为兜底用途，解析规则可能随页面结构变化而失效。
    """
    if not query:
        return []
    url = f"https://www.baidu.com/s?wd={quote(query)}"
    html = _fetch_html(url)
    if not html:
        return []

    results: List[Dict] = []
    # 标题匹配：<h3 class="t">...<a href="...">标题</a>
    title_re = re.compile(r"<h3[^>]*>\s*<a[^>]*href=\"(.*?)\"[^>]*>(.*?)</a>", re.S | re.I)
    abstract_re = re.compile(r"<div class=\"c-abstract\"[^>]*>(.*?)</div>", re.S | re.I)

    titles = list(title_re.finditer(html))
    abstracts = list(abstract_re.finditer(html))

    def _clean_text(t: str) -> str:
        return re.sub(r"<[^>]+>", "", t).strip()

    for i, m in enumerate(titles):
        href = m.group(1)
        title = _clean_text(m.group(2))
        body = ""
        if i < len(abstracts):
            body = _clean_text(abstracts[i].group(1))
        try:
            domain = urlparse(href).netloc.lower()
        except Exception:
            domain = ""
        results.append({
            "title": title,
            "href": href,
            "body": body,
            "source": domain or "baidu.com",
        })
        if len(results) >= max_results:
            break
    return results