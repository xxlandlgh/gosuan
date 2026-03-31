from __future__ import annotations

from .daily_fortune import daily_fortune
from .bazi import STEM_INFO, build_bazi_chart
from .models import AiConfig, DailyFortuneRequest, PersonProfile, WealthReport
from .openai_compat import generate_ai_text


def _pick_top_wuxing(wuxing_counts: dict[str, int]) -> tuple[list[str], list[str]]:
    items = sorted(wuxing_counts.items(), key=lambda kv: kv[1], reverse=True)
    strong = [k for k, v in items[:2] if v > 0]
    weak = [k for k, v in items[-2:] if v == items[-1][1] or v < items[0][1]]
    # 让弱项更“像弱项”
    weak = sorted(weak, key=lambda k: wuxing_counts[k])
    return strong, weak


def _build_daily_wealth_context(person: PersonProfile) -> dict[str, object]:
    today = daily_fortune(DailyFortuneRequest(person=person, tz=person.tz))
    wealth_direction = today.lucky_direction or (today.go_directions[0] if today.go_directions else None)
    return {
        "day": today.day.isoformat(),
        "wealth_direction": wealth_direction,
        "support_directions": today.go_directions,
        "avoid_directions": today.avoid_directions,
        "lucky_numbers": today.lucky_numbers,
        "lottery_numbers": today.lottery_numbers,
        "lottery_recommendations": today.lottery_recommendations,
        "stock_preferred_digits": today.stock_preferred_digits,
        "stock_avoid_digits": today.stock_avoid_digits,
        "stock_theme_keywords": today.stock_theme_keywords,
        "stock_avoid_keywords": today.stock_avoid_keywords,
        "stock_code_hints": today.stock_code_hints,
    }


def build_wealth_report(
    person: PersonProfile,
    ai: AiConfig | None = None,
) -> WealthReport:
    chart = build_bazi_chart(person)
    dm_el, dm_yy = STEM_INFO[chart.day_master]
    daily_ctx = _build_daily_wealth_context(person)

    strong, weak = _pick_top_wuxing(chart.wuxing_counts)

    overview = (
        f"日主为「{chart.day_master}」（{dm_el}{dm_yy}）。"
        f"五行结构偏向：偏旺={strong or ['无明显']}，偏弱={weak or ['无明显']}。"
        f"当天财运方位优先参考：{daily_ctx.get('wealth_direction') or '暂无'}。"
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
        "daily_wealth_context": daily_ctx,
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
    if daily_ctx.get("wealth_direction"):
        suggestions.append(
            f"当天财运方位可优先参考「{daily_ctx['wealth_direction']}」；若当天要谈钱、签单、做财务安排，可优先朝这个方向行动。"
        )
    if daily_ctx.get("support_directions"):
        suggestions.append(
            f"辅助方位可参考：{'、'.join(daily_ctx['support_directions'])}；更适合用来安排沟通、见客户、复盘账户或做轻量决策。"
        )
    if daily_ctx.get("avoid_directions"):
        cautions.append(
            f"若人在非财位/回避方位（{'、'.join(daily_ctx['avoid_directions'])}），当天更适合先做信息收集、小额试错和复盘，少做重仓与冲动决定。"
        )
    if daily_ctx.get("stock_preferred_digits"):
        suggestions.append(
            f"股票观察可偏向数字/代码含 {'、'.join(str(x) for x in daily_ctx['stock_preferred_digits'])} 的标的，同时结合 {'、'.join(daily_ctx.get('stock_theme_keywords') or [])} 这类主题词筛选。"
        )
    if daily_ctx.get("stock_avoid_digits"):
        cautions.append(
            f"当天可少碰代码尾号或主体数字反复落在 {'、'.join(str(x) for x in daily_ctx['stock_avoid_digits'])} 的标的，尤其叠加 {'、'.join(daily_ctx.get('stock_avoid_keywords') or [])} 时更要保守。"
        )
    if daily_ctx.get("lottery_numbers"):
        suggestions.append(
            f"彩票娱乐可优先参考通用号 {'、'.join(str(x) for x in daily_ctx['lottery_numbers'])}，并结合分彩种模板做娱乐化选择。"
        )

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
你是一位严谨的命理分析师，擅长把八字结构和当天黄历信息转成“更实际的财运建议”。要求：
1) 避免迷信口吻，不做确定性承诺，不直接给具体股票买卖指令；
2) 只输出与此人相关的内容，必须引用下方结构字段，不要泛泛而谈；
3) 你的输出必须严格使用下面 4 个一级标题，顺序不能变，标题文字也不能改：
   一、股票偏好
   二、彩票偏好
   三、财位处理
   四、今日忌讳
4) 每个一级标题下面都必须输出 3-5 条短句，优先写可直接照做的内容；
5) 「一、股票偏好」必须覆盖：
   - 宜偏向哪些数字/代码特征
   - 宜偏向哪些名称或题材关键词
   - 忌讳哪些数字或题材关键词
   - 但不要直接写“买某只股票”或给出具体买入价位
6) 「二、彩票偏好」必须覆盖：
   - 宜偏向哪些数字组合
   - 哪些数字尽量少碰
   - 可直接引用给定娱乐号，但必须注明仅供娱乐
7) 「三、财位处理」必须覆盖：
   - 当天财运方位
   - 辅助方位
   - 如果人在非财位或回避方位，应当怎么处理
8) 「四、今日忌讳」必须覆盖：
   - 今天最该避开的财务动作
   - 今天最该避开的股票/彩票相关冲动行为
   - 一条收尾提醒
9) 当你写“名称偏向”时，优先用“关键词/字眼倾向”表达，例如偏向稳健、央国企、高股息、业绩兑现之类，不要编造上市公司名称；
10) 语言：中文简体，直给、具体、可落地，尽量写成用户能直接照着做的建议。

个人信息：
- 姓名/称呼：{person.name}
- 性别：{person.gender.value}
- 出生：{person.birth_dt.isoformat()}（{person.tz}）

命盘结构（JSON）：
{struct}

已有建议（供你参考，但你必须写得更个性化、更细）：
- 建议：{report.suggestions}
- 注意：{report.cautions}

再次强调：
- 输出时不要出现 “A.”、“B.”、“总结”、“结论”、“行动计划” 这些额外一级标题；
- 只能输出上述四个一级标题；
- 不要输出 JSON、表格或代码块。
""".strip()

