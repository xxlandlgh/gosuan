from __future__ import annotations

from .bazi import STEM_INFO, build_bazi_chart
from .models import AiConfig, PersonProfile, WealthReport
from .openai_compat import generate_ai_text


def _pick_top_wuxing(wuxing_counts: dict[str, int]) -> tuple[list[str], list[str]]:
    items = sorted(wuxing_counts.items(), key=lambda kv: kv[1], reverse=True)
    strong = [k for k, v in items[:2] if v > 0]
    weak = [k for k, v in items[-2:] if v == items[-1][1] or v < items[0][1]]
    # 让弱项更“像弱项”
    weak = sorted(weak, key=lambda k: wuxing_counts[k])
    return strong, weak


def build_wealth_report(
    person: PersonProfile,
    ai: AiConfig | None = None,
) -> WealthReport:
    chart = build_bazi_chart(person)
    dm_el, dm_yy = STEM_INFO[chart.day_master]

    strong, weak = _pick_top_wuxing(chart.wuxing_counts)

    overview = (
        f"日主为「{chart.day_master}」（{dm_el}{dm_yy}）。"
        f"五行结构偏向：偏旺={strong or ['无明显']}，偏弱={weak or ['无明显']}。"
        "财运解读以“结构与行为策略”为主，避免把结果当作投资承诺。"
    )

    structure = {
        "day_master": {"stem": chart.day_master, "element": dm_el, "polarity": dm_yy},
        "pillars": {
            "year": chart.year.model_dump(),
            "month": chart.month.model_dump(),
            "day": chart.day.model_dump(),
            "hour": chart.hour.model_dump(),
        },
        "wuxing_counts": chart.wuxing_counts,
        "ten_gods": chart.shishen,
        "zodiac": chart.raw.get("lunar", {}).get("animal"),
    }

    suggestions: list[str] = []
    cautions: list[str] = []

    # 结构化建议：用“十神 + 五行偏旺偏弱”做可执行建议
    # 注意：不做“必然发财/必然破财”断语；只给策略
    if "正财" in chart.shishen.values() or "偏财" in chart.shishen.values():
        suggestions.append("命盘天干透财，适合做“可量化的进出账管理”：预算、复盘、固定周期结算。")
    else:
        suggestions.append("命盘天干不显财，建议把重心放在“提升可复制的技能/产能”，让收入来自长期积累。")

    if "伤官" in chart.shishen.values():
        cautions.append("有伤官象，容易因情绪/冲动决策导致财务波动；重大支出建议设置冷静期。")
    if "七杀" in chart.shishen.values():
        cautions.append("七杀象更吃“规则与风控”；借贷、杠杆、合伙需把合同与退出机制写清。")
    if "正印" in chart.shishen.values() or "偏印" in chart.shishen.values():
        suggestions.append("印星象偏强时，学习与证书/资质对财运提升更明显；建议投资在系统化学习。")

    if weak:
        suggestions.append(f"五行偏弱方向（{ '、'.join(weak) }）可用“时间/环境/习惯”补足：作息稳定、规律运动、减少高波动社交消费。")
    if strong:
        cautions.append(f"五行偏旺方向（{ '、'.join(strong) }）要防“用力过猛”：避免单一赛道/单一资产过度集中。")

    report = WealthReport(
        overview=overview,
        structure=structure,
        suggestions=suggestions,
        cautions=cautions,
    )

    if ai and ai.enabled:
        prompt = _build_wealth_prompt(person, report)
        ai_res = generate_ai_text(prompt=prompt, ai=ai)
        report.ai_text = ai_res.text

    return report


def _build_wealth_prompt(person: PersonProfile, report: WealthReport) -> str:
    struct = report.structure
    return f"""
你是一位严谨的命理分析师，擅长把八字结构转成“可执行的财务策略建议”。要求：
1) 避免迷信口吻，不做确定性承诺，不给投资买卖点；
2) 只输出与此人相关的内容，必须引用下方结构字段，不要泛泛而谈；
3) 输出：A.财运结构画像 B.容易漏财的行为模式 C.适合的赚钱方式与行业倾向（用“倾向/更适合”措辞） D.三条可执行的30天行动计划；
4) 语言：中文简体，直给、具体、可落地。

个人信息：
- 姓名/称呼：{person.name}
- 性别：{person.gender.value}
- 出生：{person.birth_dt.isoformat()}（{person.tz}）

命盘结构（JSON）：
{struct}

已有建议（供你参考，但你必须写得更个性化、更细）：
- 建议：{report.suggestions}
- 注意：{report.cautions}
""".strip()

