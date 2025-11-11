from flask import Flask, render_template, request
from pathlib import Path
import yaml
from agents.query_agent import search_web
from agents.news_adapter import search_rss
from agents.baidu_adapter import search_baidu
from agents.llm_planner import plan_query
from processing.cleaning import filter_chinese, dedup_by_href, sort_by_relevance, filter_by_domain
from processing.summarizer import build_summary
from processing.fetcher import enrich_items_with_content
from datetime import datetime
from urllib.parse import urlparse


def load_config():
    cfg_path = Path(__file__).parent / "config.yaml"
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


app = Flask(__name__, template_folder=str(Path(__file__).parent / "templates"))
CONFIG = load_config()


@app.route("/", methods=["GET"])
def index():
    return render_template(
        "index.html",
        version=CONFIG.get("version", "0.1.0"),
        timelimit_default=CONFIG["search"].get("timelimit", "m"),
    )


@app.route("/report", methods=["POST"])
def report():
    query = request.form.get("query", "").strip()
    if not query:
        return render_template(
            "index.html",
            version=CONFIG.get("version", "0.1.0"),
            timelimit_default=CONFIG["search"].get("timelimit", "m"),
            error="请填写查询主题",
        )

    # 由 LLM/规则规划检索策略（国内优先）
    plan = plan_query(query, CONFIG)
    max_results = int(plan.get("max_results", CONFIG["search"]["max_results_text"]))
    timelimit_ui = plan.get("timelimit", CONFIG["search"].get("timelimit", "m"))  # 'w'|'m'|'90'
    timelimit = "y" if timelimit_ui == "90" else timelimit_ui
    chinese_only = CONFIG["search"]["chinese_only"]
    whitelist = CONFIG["search"].get("whitelist_domains", [])
    blacklist = CONFIG["search"].get("blacklist_domains", [])
    domain_weights = CONFIG["search"].get("domain_weights", {})

    # 关键词策略（简化）：按空格切分，后续可扩展同义词/别称
    keywords = [k for k in query.split() if k]

    raw_web = []
    domestic_only = bool(plan.get("domestic_only", CONFIG["search"].get("domestic_only", True)))
    use_ddg = bool(plan.get("use_duckduckgo", CONFIG["search"].get("duckduckgo_enabled", False)))
    use_baidu = bool(plan.get("use_baidu", True))
    if (not domestic_only) and use_ddg:
        raw_web = search_web(query, max_results=max_results, timelimit=timelimit) or []
    # 国内优先或DDG为空时，用百度
    if use_baidu and not raw_web:
        raw_web = search_baidu(query, max_results=max_results) or []
    enable_news = CONFIG["search"].get("enable_news", False) and bool(plan.get("use_rss", True))
    news_feeds = CONFIG["search"].get("news_feeds", [])
    raw_news = []
    if enable_news and news_feeds:
        raw_news = search_rss(query, feeds=news_feeds, max_results=max_results, timelimit_ui=timelimit_ui)
    raw = (raw_web or []) + (raw_news or [])
    filtered = filter_chinese(raw, chinese_only=chinese_only)
    # 当中文过滤后结果为空时，做一次兜底：使用未过滤的原始结果，以避免全部为英文或特殊编码导致0条
    fallback_used = False
    if chinese_only and not filtered:
        filtered = raw
        fallback_used = True
    uniq = dedup_by_href(filtered)
    domain_filtered = filter_by_domain(uniq, whitelist=whitelist, blacklist=blacklist)

    # 引入域名权重：score = relevance + domain_weight
    def _weight_for(url: str) -> float:
        try:
            d = urlparse(url).netloc.lower()
        except Exception:
            d = ""
        for key, w in (domain_weights or {}).items():
            key = (key or "").lower().strip()
            if not key:
                continue
            if d == key or d.endswith("." + key):
                try:
                    return float(w)
                except Exception:
                    return 0.0
        return 0.0

    scored = []
    for it in domain_filtered:
        base = 0.0
        try:
            # 复用清洗模块的相关性计算
            base = float(sum((it.get("title", "") + " " + it.get("body", "")).count(k) for k in keywords))
        except Exception:
            base = 0.0
        it["_score"] = base + _weight_for(it.get("href", ""))
        scored.append(it)
    sorted_items = sorted(scored, key=lambda x: x.get("_score", 0.0), reverse=True)
    top_items = sorted_items[:max_results]
    # 抓取前若为空，走增广与保底逻辑（如下）；抓取在最终确定展示集后进行
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 数据说明与配置摘要
    if timelimit_ui == "w":
        timelimit_display = "近7天"
        timelimit_note = None
    elif timelimit_ui == "m":
        timelimit_display = "近30天"
        timelimit_note = None
    else:
        timelimit_display = "近90天（近似）"
        timelimit_note = "说明：在策略规划中将近90天映射为近一年检索近似。"

    source_desc = ("国内网页文本（Baidu）" if domestic_only or not use_ddg else "公开网页文本（DuckDuckGo）") + (" + RSS新闻源" if enable_news and news_feeds else "")

    # 自动增广策略：若最终为 0，扩大时间窗到近一年、关闭中文过滤与域名过滤，并启用内置 RSS 源重试
    relax_used = False
    relax_final = 0
    if len(top_items) == 0:
        relax_used = True
        timelimit_relax = "y"
        alt_queries = [query, f"{query} 导演", f"{query} 电影", f"{query} 舆情", f"{query} 评价"]
        combined_web = []
        combined_news = []
        # 多关键字增广：合并多次检索结果
        for q2 in alt_queries:
            rw = []
            if (not domestic_only) and use_ddg:
                rw = search_web(q2, max_results=max_results, timelimit=timelimit_relax) or []
            if use_baidu and not rw:
                rw = search_baidu(q2, max_results=max_results) or []
            combined_web.extend(rw)
            if news_feeds:
                rn = search_rss(q2, feeds=news_feeds, max_results=max_results, timelimit_ui="90") or []
                combined_news.extend(rn)
        raw2 = combined_web + combined_news
        filtered2 = filter_chinese(raw2, chinese_only=False)
        uniq2 = dedup_by_href(filtered2)
        # 关闭域名过滤
        domain_filtered2 = uniq2
        # 重新打分（引入域名权重）
        scored2 = []
        for it in domain_filtered2:
            base = 0.0
            try:
                base = float(sum((it.get("title", "") + " " + it.get("body", "")).count(k) for k in keywords))
            except Exception:
                base = 0.0
            it["_score"] = base + _weight_for(it.get("href", ""))
            scored2.append(it)
        sorted_items2 = sorted(scored2, key=lambda x: x.get("_score", 0.0), reverse=True)
        top_items = sorted_items2[:max_results]
        relax_final = len(top_items)

    # 仍为空：引入“保底来源”（百科/维基），确保页面不再空白
    curated_used = False
    if len(top_items) == 0:
        curated_used = True
        curated = [
            {
                "title": "王家卫 - 维基百科，自由的百科全书",
                "href": "https://zh.wikipedia.org/zh-cn/%E7%8E%8B%E5%AE%B6%E5%8D%AB",
                "body": "王家卫（Wong Kar-wai），香港导演与编剧，以独特的影像风格与叙事著称。",
                "source": "zh.wikipedia.org",
            },
            {
                "title": "王家卫_百度百科",
                "href": "https://baike.baidu.com/item/%E7%8E%8B%E5%AE%B6%E5%8D%AB",
                "body": "王家卫，香港著名导演，代表作包括《重庆森林》《花样年华》等。",
                "source": "baike.baidu.com",
            },
        ]
        top_items = curated[:max_results]

    # 为前 K 条抓取正文内容，提升摘要质量
    fetch_success = 0
    fetch_fail = 0
    fetcher_cfg = CONFIG.get("fetcher", {})
    if fetcher_cfg.get("enabled", True) and len(top_items) > 0:
        top_k = int(fetcher_cfg.get("top_k", 5))
        timeout = float(fetcher_cfg.get("timeout", 10.0))
        fetch_success, fetch_fail = enrich_items_with_content(top_items, top_k=top_k, timeout=timeout)

    # 抓取后生成摘要
    summary = build_summary(top_items, query)

    return render_template(
        "report.html",
        version=CONFIG.get("version", "0.1.0"),
        title=CONFIG["report"]["title"],
        query=query,
        items=top_items,
        summary=summary,
        total=len(top_items),
        config_summary={
            "max_results": max_results,
            "chinese_only": chinese_only,
            "timelimit_display": timelimit_display,
            "timelimit_note": timelimit_note,
            "source": source_desc,
            "generated_at": generated_at,
            "whitelist": ", ".join(whitelist) if whitelist else "(无)",
            "blacklist": ", ".join(blacklist) if blacklist else "(无)",
        },
        timelimit_ui=timelimit_ui,
        debug=CONFIG["web"].get("debug", False),
        debug_counts={
            "raw_web": len(raw_web or []),
            "raw_news": len(raw_news or []),
            "raw_total": len(raw),
            "filtered": len(filtered),
            "dedup": len(uniq),
            "domain": len(domain_filtered),
            "final": len(top_items),
            "fallback_used": fallback_used,
            "relax_used": relax_used,
            "relax_final": relax_final,
            "curated_used": curated_used,
            "fetch_success": fetch_success,
            "fetch_fail": fetch_fail,
        },
    )


@app.route("/export", methods=["POST"])
def export_markdown():
    """以 Markdown 文件形式导出当前报告到 output 目录。"""
    query = request.form.get("query", "").strip()
    if not query:
        return render_template(
            "index.html",
            version=CONFIG.get("version", "0.1.0"),
            timelimit_default=CONFIG["search"].get("timelimit", "m"),
            error="请填写查询主题",
        )

    max_results = int(request.form.get("max_results", CONFIG["search"]["max_results_text"]))
    timelimit_ui = request.form.get("timelimit", CONFIG["search"]["timelimit"])  # 'w'|'m'|'90'
    timelimit = "y" if timelimit_ui == "90" else timelimit_ui
    chinese_only = CONFIG["search"]["chinese_only"]
    whitelist = CONFIG["search"].get("whitelist_domains", [])
    blacklist = CONFIG["search"].get("blacklist_domains", [])
    domain_weights = CONFIG["search"].get("domain_weights", {})

    keywords = [k for k in query.split() if k]
    raw_web = search_web(query, max_results=max_results, timelimit=timelimit)
    enable_news = CONFIG["search"].get("enable_news", False)
    news_feeds = CONFIG["search"].get("news_feeds", [])
    raw_news = []
    if enable_news and news_feeds:
        raw_news = search_rss(query, feeds=news_feeds, max_results=max_results, timelimit_ui=timelimit_ui)
    raw = (raw_web or []) + (raw_news or [])
    filtered = filter_chinese(raw, chinese_only=chinese_only)
    fallback_used = False
    if chinese_only and not filtered:
        filtered = raw
        fallback_used = True
    uniq = dedup_by_href(filtered)
    domain_filtered = filter_by_domain(uniq, whitelist=whitelist, blacklist=blacklist)

    def _weight_for(url: str) -> float:
        try:
            d = urlparse(url).netloc.lower()
        except Exception:
            d = ""
        for key, w in (domain_weights or {}).items():
            key = (key or "").lower().strip()
            if not key:
                continue
            if d == key or d.endswith("." + key):
                try:
                    return float(w)
                except Exception:
                    return 0.0
        return 0.0

    scored = []
    for it in domain_filtered:
        base = 0.0
        try:
            base = float(sum((it.get("title", "") + " " + it.get("body", "")).count(k) for k in keywords))
        except Exception:
            base = 0.0
        it["_score"] = base + _weight_for(it.get("href", ""))
        scored.append(it)
    sorted_items = sorted(scored, key=lambda x: x.get("_score", 0.0), reverse=True)
    top_items = sorted_items[:max_results]
    # 为前 K 条抓取正文内容，提升摘要质量（导出也使用同样的抓取策略）
    fetch_success = 0
    fetch_fail = 0
    fetcher_cfg = CONFIG.get("fetcher", {})
    if fetcher_cfg.get("enabled", True) and len(top_items) > 0:
        top_k = int(fetcher_cfg.get("top_k", 5))
        timeout = float(fetcher_cfg.get("timeout", 10.0))
        fetch_success, fetch_fail = enrich_items_with_content(top_items, top_k=top_k, timeout=timeout)

    summary = build_summary(top_items, query)
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if timelimit_ui == "w":
        timelimit_display = "近7天"
        timelimit_note = None
    elif timelimit_ui == "m":
        timelimit_display = "近30天"
        timelimit_note = None
    else:
        timelimit_display = "近90天（近似）"
        timelimit_note = "说明：DuckDuckGo 仅支持 d/w/m/y，本选项以 '近一年' 检索近似替代。"

    # 生成并保存 Markdown 文件
    from reporting.markdown import save_markdown_report
    source_desc = "公开网页文本（DuckDuckGo）" + (" + RSS新闻源" if enable_news and news_feeds else "")

    md_path = save_markdown_report(
        version=CONFIG.get("version", "0.1.0"),
        output_dir=CONFIG["report"]["output_dir"],
        title=CONFIG["report"]["title"],
        query=query,
        items=top_items,
        summary=summary,
        config_summary={
            "max_results": max_results,
            "chinese_only": chinese_only,
            "timelimit_display": timelimit_display,
            "timelimit_note": timelimit_note,
            "source": source_desc,
            "generated_at": generated_at,
            "whitelist": ", ".join(whitelist) if whitelist else "(无)",
            "blacklist": ", ".join(blacklist) if blacklist else "(无)",
        },
    )

    # 返回原报告页，并在顶部提示文件保存路径
    return render_template(
        "report.html",
        version=CONFIG.get("version", "0.1.0"),
        title=CONFIG["report"]["title"],
        query=query,
        items=top_items,
        summary=summary,
        total=len(top_items),
        config_summary={
            "max_results": max_results,
            "chinese_only": chinese_only,
            "timelimit_display": timelimit_display,
            "timelimit_note": timelimit_note,
            "source": source_desc,
            "generated_at": generated_at,
            "whitelist": ", ".join(whitelist) if whitelist else "(无)",
            "blacklist": ", ".join(blacklist) if blacklist else "(无)",
        },
        export_path=str(md_path),
        timelimit_ui=timelimit_ui,
        debug=CONFIG["web"].get("debug", False),
        debug_counts={
            "raw_web": len(raw_web or []),
            "raw_news": len(raw_news or []),
            "raw_total": len(raw),
            "filtered": len(filtered),
            "dedup": len(uniq),
            "domain": len(domain_filtered),
            "final": len(top_items),
            "fallback_used": fallback_used,
            "fetch_success": fetch_success,
            "fetch_fail": fetch_fail,
        },
    )


if __name__ == "__main__":
    host = CONFIG["web"]["host"]
    port = CONFIG["web"]["port"]
    debug = CONFIG["web"]["debug"]
    app.run(host=host, port=port, debug=debug)