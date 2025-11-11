"""
搜索与来源适配器的自动化冒烟测试。

运行：
  python 舆情分析/mvp/tests/search_smoke.py

目标：
  - 验证 duckduckgo 文本/新闻检索在不同区域与时间窗下是否能返回结果
  - 验证 RSS 适配器在启用情况下是否能返回结果
  - 对典型中文主题（如“王家卫”）进行多关键词组合测试

注意：
  - 若网络受限或依赖缺失，结果可能为 0；脚本会给出明确提示
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # 指向 舆情分析 目录
MVP_DIR = ROOT / "mvp"
sys.path.append(str(MVP_DIR))

from agents.query_agent import search_web
from agents.baidu_adapter import search_baidu
from agents.news_adapter import search_rss, _lazy_feedparser  # type: ignore
import yaml


def load_config():
    cfg_path = MVP_DIR / "config.yaml"
    return yaml.safe_load(cfg_path.read_text(encoding="utf-8"))


def show(title: str):
    print("\n== " + title)


def try_ddg(query: str, timelimit: str, max_results: int = 20):
    res = search_web(query, max_results=max_results, timelimit=timelimit)
    print(f"DuckDuckGo({timelimit}) -> {len(res)} 条")
    for i, it in enumerate(res[:5], 1):
        print(f"  {i}. [{it.get('source','')}] {it.get('title','')}")
    return res


def try_rss(query: str, cfg: dict, timelimit_ui: str = "m", max_results: int = 20):
    feeds = cfg.get("search", {}).get("news_feeds", [])
    fp = _lazy_feedparser()
    if not fp:
        print("RSS -> 依赖未安装(feedparser)，返回 0 条")
        return []
    res = search_rss(query, feeds=feeds, max_results=max_results, timelimit_ui=timelimit_ui)
    print(f"RSS({timelimit_ui}) -> {len(res)} 条")
    for i, it in enumerate(res[:5], 1):
        print(f"  {i}. [{it.get('source','')}] {it.get('title','')}")
    return res


def main():
    cfg = load_config()
    queries = [
        "王家卫",
        "王家卫 导演",
        "王家卫 电影",
        "王家卫 Wong Kar-wai",
    ]

    show("冒烟测试：DuckDuckGo 文本/新闻 + RSS")
    for q in queries:
        print(f"\n主题：{q}")
        # 文本检索（月）
        _ = try_ddg(q, timelimit="m")
        # 文本检索（年）
        _ = try_ddg(q, timelimit="y")
        # 百度兜底检索
        res_baidu = search_baidu(q, max_results=20)
        print(f"Baidu -> {len(res_baidu)} 条")
        for i, it in enumerate(res_baidu[:5], 1):
            print(f"  {i}. [{it.get('source','')}] {it.get('title','')}")
        # RSS（近30天）
        _ = try_rss(q, cfg, timelimit_ui="m")

    print("\n完成：若上述全部为 0 条，说明当前网络受限或依赖缺失（请检查 duckduckgo-search 与 feedparser）。")


if __name__ == "__main__":
    main()