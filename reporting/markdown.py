from pathlib import Path
from datetime import datetime
import re


def sanitize_filename(name: str) -> str:
    name = name.strip()
    name = re.sub(r"\s+", "_", name)
    # 去除不适合作为文件名的字符
    name = re.sub(r"[^\w\-_.]", "", name)
    return name or "report"


def build_markdown(version: str, title: str, query: str, items, summary: str, config_summary: dict) -> str:
    lines = []
    lines.append(f"# {title} v{version}")
    lines.append("")
    lines.append(f"**主题**：{query}")
    lines.append(f"**生成时间**：{config_summary.get('generated_at')}")
    lines.append(f"**时间窗**：{config_summary.get('timelimit_display')}" + (f"（{config_summary.get('timelimit_note')}）" if config_summary.get('timelimit_note') else ""))
    lines.append(f"**结果配额**：{config_summary.get('max_results')}")
    lines.append(f"**语言过滤**：仅中文（{'是' if config_summary.get('chinese_only') else '否'}）")
    lines.append(f"**来源类型**：{config_summary.get('source')}")
    lines.append(f"**白名单**：{config_summary.get('whitelist')}")
    lines.append(f"**黑名单**：{config_summary.get('blacklist')}")
    lines.append("")
    lines.append("## 总览结论（草案）")
    lines.append(summary or "（暂无结论）")
    lines.append("")
    lines.append("## 代表性文本结果")
    for i, it in enumerate(items, start=1):
        title = it.get("title", "")
        href = it.get("href", "")
        source = it.get("source", "")
        body = it.get("body", "")
        lines.append(f"{i}. [{title}]({href})  — 来源：{source}")
        if body:
            lines.append(f"   - 摘要：{body}")
    lines.append("")
    lines.append("## 风险与建议（草案）")
    lines.append("- 当前为文本MVP，建议后续补充平台覆盖与评论层抓取。")
    lines.append("- 建议逐步接入多模态与内部库，以提高结论稳健性与说服力。")
    lines.append("")
    lines.append("## 数据说明与免责声明")
    lines.append("- 本报告仅供参考，数据来源为公开网页文本，可能存在采样偏差与时效性限制。")
    return "\n".join(lines)


def save_markdown_report(version: str, output_dir: str, title: str, query: str, items, summary: str, config_summary: dict) -> Path:
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fn_query = sanitize_filename(query)
    filename = f"{ts}_v{version}_{fn_query}.md"
    md = build_markdown(version=version, title=title, query=query, items=items, summary=summary, config_summary=config_summary)
    path = out_dir / filename
    path.write_text(md, encoding="utf-8")
    return path