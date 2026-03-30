from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .models import BaziChart, DailyFortuneResponse, DateSchool, Purpose, WealthReport


PURPOSE_CN: dict[Purpose, str] = {
    Purpose.move: "搬迁/入宅",
    Purpose.construction: "动工/装修",
    Purpose.opening: "开业/开市",
    Purpose.wedding: "婚嫁",
}

SCHOOL_CN: dict[DateSchool, str] = {
    DateSchool.best_fit: "最匹配（宜忌+建除+冲破）",
    DateSchool.strict: "严格（必须宜+强吉建除+避冲破）",
    DateSchool.almanac: "仅黄历宜忌",
    DateSchool.jianchu: "仅建除十二神",
}

WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]


def weekday_cn(d: date) -> str:
    return WEEKDAY_CN[d.weekday()]


def purpose_cn(p: Purpose) -> str:
    return PURPOSE_CN.get(p, p.value)


def school_cn(s: DateSchool) -> str:
    return SCHOOL_CN.get(s, s.value)


def summarize_candidate(*, purpose: Purpose, candidate: dict) -> list[str]:
    """
    candidate 是 DateCandidate 的 model_dump() 结果。
    输出“解析”字段（可解释、可读），避免只是堆原始 JSON。
    """
    lines: list[str] = []
    raw = (candidate.get("raw") or {}) if isinstance(candidate, dict) else {}
    yi = raw.get("yi") or []
    ji = raw.get("ji") or []
    jianchu = raw.get("jianchu_12")
    zodiac = raw.get("zodiac")
    day_branch = raw.get("day_branch")
    month_branch = raw.get("month_branch")
    year_branch = raw.get("year_branch")

    if zodiac:
        lines.append(f"命主生肖：{zodiac}（用于判断六冲）。")
    if jianchu:
        lines.append(f"建除十二神：{jianchu}（作为结构性择日依据之一）。")
    if day_branch and month_branch:
        lines.append(f"日支：{day_branch}；月支：{month_branch}（用于月破判断）。")
    if day_branch and year_branch:
        lines.append(f"日支：{day_branch}；年支：{year_branch}（用于岁破判断）。")
    if yi:
        lines.append(f"黄历宜（节选）：{ '、'.join(yi[:10]) }。")
    if ji:
        lines.append(f"黄历忌（节选）：{ '、'.join(ji[:10]) }。")

    # 目的导向的轻量总结
    lines.append(f"本次目的：{purpose_cn(purpose)}。建议优先看“理由/提醒”与是否符合你实际安排。")
    return lines


def _join_list(items: list[str], empty: str = "暂无") -> str:
    return "、".join(items) if items else empty


def format_bazi_text(name: str, chart: BaziChart) -> str:
    pillars = (
        f"年柱 {chart.year.stem}{chart.year.branch}",
        f"月柱 {chart.month.stem}{chart.month.branch}",
        f"日柱 {chart.day.stem}{chart.day.branch}",
        f"时柱 {chart.hour.stem}{chart.hour.branch}",
    )
    wuxing_sorted = sorted(chart.wuxing_counts.items(), key=lambda kv: kv[1], reverse=True)
    wuxing_text = "，".join(f"{k}{v}" for k, v in wuxing_sorted)
    shishen_text = "，".join(f"{k}:{v}" for k, v in chart.shishen.items())
    zodiac = chart.raw.get("lunar", {}).get("animal", "未知")
    return "\n".join(
        [
            f"{name}的八字命盘",
            f"四柱：{' | '.join(pillars)}",
            f"日主：{chart.day_master}",
            f"生肖：{zodiac}",
            f"五行分布：{wuxing_text}",
            f"十神结构：{shishen_text}",
            "提示：这是结构化排盘结果，适合拿来做后续解读或规则扩展。",
        ]
    )


def format_wealth_text(name: str, report: WealthReport) -> str:
    lines = [
        f"{name}的财运结构简报",
        report.overview,
        "",
        "适合优先做的事：",
    ]
    if report.suggestions:
        lines.extend(f"- {x}" for x in report.suggestions)
    else:
        lines.append("- 暂无明显建议。")

    lines.extend(["", "需要特别留意："])
    if report.cautions:
        lines.extend(f"- {x}" for x in report.cautions)
    else:
        lines.append("- 当前没有特别突出的风险提示。")

    if report.ai_text:
        lines.extend(["", "AI 补充解读：", report.ai_text.strip()])
    return "\n".join(lines)


def format_daily_fortune_text(name: str, resp: DailyFortuneResponse) -> str:
    lines = [
        f"{name}在 {resp.day.isoformat()} 的个人运势",
        f"生肖：{resp.zodiac} | 日干支：{resp.day_ganzhi} | 建除：{resp.jianchu_12}",
        f"黄历宜：{_join_list(resp.yi, '无明显宜项')}",
        f"黄历忌：{_join_list(resp.ji, '无明显忌项')}",
        "",
        "今天更适合：",
    ]
    lines.extend([f"- {x}" for x in resp.good] or ["- 暂无特别突出的加分事项。"])
    lines.extend(["", "今天尽量避开："])
    lines.extend([f"- {x}" for x in resp.bad] or ["- 暂无特别明确的避坑项。"])
    lines.extend(
        [
            "",
            f"适合去的方位：{_join_list(resp.go_directions, '可按实际行程安排')}",
            f"尽量回避的方位：{_join_list(resp.avoid_directions, '暂无特别提示')}",
        ]
    )
    if resp.notes:
        lines.extend(["", "补充提醒："])
        lines.extend(f"- {x}" for x in resp.notes)
    return "\n".join(lines)


def format_divination_text(name: str, result: dict) -> str:
    upper = result.get("upper", {})
    lower = result.get("lower", {})
    moving_line = result.get("moving_line")
    method = result.get("method", "未知方法")
    return "\n".join(
        [
            f"{name}的起卦结果",
            f"上卦：{upper.get('name', '未知')}{upper.get('symbol', '')}（{upper.get('element', '未知')}）",
            f"下卦：{lower.get('name', '未知')}{lower.get('symbol', '')}（{lower.get('element', '未知')}）",
            f"动爻：第 {moving_line} 爻",
            f"起卦方式：{method}",
            "提示：这个结果适合拿去做后续断卦，不建议单独把一句吉凶当结论。",
        ]
    )


def format_select_date_text(*, name: str, purpose: Purpose, school: DateSchool, payload: dict) -> str:
    candidates = payload.get("候选日") or []
    lines = [
        f"{name}的择日建议",
        f"目的：{purpose_cn(purpose)}",
        f"流派：{school_cn(school)}",
        f"范围：{payload.get('开始日期')} 至 {payload.get('结束日期')}",
    ]
    if not candidates:
        lines.append("结果：这段时间里没有筛出合适日期，建议放宽条件或换一个时间段再试。")
        return "\n".join(lines)

    lines.extend(["", "推荐日期："])
    for idx, item in enumerate(candidates, start=1):
        reasons = _join_list(item.get("理由") or [], "暂无明显加分点")
        warnings = _join_list(item.get("提醒") or [], "暂无明显风险提示")
        lines.append(
            f"{idx}. {item.get('日期')} {item.get('星期')} | 评分 {item.get('评分')} | 理由：{reasons} | 提醒：{warnings}"
        )
    lines.append("")
    lines.append("说明：评分越高，代表在当前规则下越适合作为优先候选，但最终仍建议结合你自己的实际安排。")
    return "\n".join(lines)

