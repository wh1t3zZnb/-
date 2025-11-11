"""
Content Fetcher（MVP版）
- 目标：在检索到的链接中抓取网页正文，用于更高质量的摘要与倾向判断。
- 设计：尽量依赖轻量；优先 httpx，其次 requests，最后 urllib；正文抽取优先 lxml，失败则回退简单去标签。
"""

from typing import Optional, Tuple, List, Dict

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/118.0 Safari/537.36"
)


def _fetch_html(url: str, timeout: float = 10.0, max_bytes: int = 1000_000) -> Optional[str]:
    html: Optional[str] = None
    # 优先 httpx
    try:
        import httpx

        with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=timeout) as client:
            r = client.get(url)
            if r.status_code == 200:
                text = r.text
                if text and len(text) > max_bytes:
                    text = text[:max_bytes]
                html = text
    except Exception:
        pass
    if html:
        return html

    # 次选 requests
    try:
        import requests

        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        if r.status_code == 200:
            text = r.text
            if text and len(text) > max_bytes:
                text = text[:max_bytes]
            html = text
    except Exception:
        pass
    if html:
        return html

    # 兜底 urllib
    try:
        import urllib.request

        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read(max_bytes)
            html = data.decode("utf-8", errors="ignore")
    except Exception:
        pass
    return html


def _extract_main_text(html: str) -> str:
    # 优先 lxml 提取正文段落
    try:
        from lxml import html as lxml_html

        doc = lxml_html.fromstring(html)
        # 优先取 <article>, <main> 中的段落，其次全局 p
        xpath_candidates = [
            "//article//p",
            "//main//p",
            "//div[contains(@class,'content') or contains(@id,'content')]//p",
            "//p",
        ]
        texts: List[str] = []
        for xp in xpath_candidates:
            ps = doc.xpath(xp)
            texts = [
                " ".join(" ".join(p.itertext()).split())
                for p in ps[:40]  # 限制段落数，避免过长
            ]
            if texts:
                break
        content = "\n".join([t for t in texts if t and len(t) >= 20])
        if content:
            return content
    except Exception:
        pass

    # 回退：粗略去脚本与标签
    import re

    html2 = re.sub(r"<script[\s\S]*?</script>", "", html, flags=re.I)
    html2 = re.sub(r"<style[\s\S]*?</style>", "", html2, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", html2)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def fetch_content(url: str, timeout: float = 10.0) -> Tuple[bool, Optional[str]]:
    """抓取并抽取正文，返回 (success, content)。"""
    try:
        html = _fetch_html(url, timeout=timeout)
        if not html:
            return False, None
        content = _extract_main_text(html)
        if not content:
            return False, None
        return True, content
    except Exception:
        return False, None


def enrich_items_with_content(items: List[Dict], top_k: int = 5, timeout: float = 10.0) -> Tuple[int, int]:
    """为前 top_k 条目抓取正文，并写入 item['content']。
    返回 (成功数, 失败数)。
    """
    success = 0
    fail = 0
    for it in items[: max(0, top_k)]:
        url = it.get("href")
        if not url:
            continue
        ok, content = fetch_content(url, timeout=timeout)
        if ok and content:
            it["content"] = content
            success += 1
        else:
            fail += 1
    return success, fail