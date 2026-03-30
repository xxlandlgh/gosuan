from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from lunar_python import Solar  # type: ignore

from .bazi import build_bazi_chart, zodiac_from_birth
from .models import DateCandidate, DateSchool, DateSelectRequest, DateSelectResponse, Purpose


ZODIAC_TO_BRANCH: dict[str, str] = {
    "鼠": "子",
    "牛": "丑",
    "虎": "寅",
    "兔": "卯",
    "龙": "辰",
    "蛇": "巳",
    "马": "午",
    "羊": "未",
    "猴": "申",
    "鸡": "酉",
    "狗": "戌",
    "猪": "亥",
}

BRANCH_CHONG: dict[str, str] = {
    "子": "午",
    "丑": "未",
    "寅": "申",
    "卯": "酉",
    "辰": "戌",
    "巳": "亥",
    "午": "子",
    "未": "丑",
    "申": "寅",
    "酉": "卯",
    "戌": "辰",
    "亥": "巳",
}

PURPOSE_KEYWORDS_YI: dict[Purpose, list[str]] = {
    Purpose.move: ["入宅", "移徙", "安床", "搬家"],
    Purpose.construction: ["动土", "修造", "开工", "装修"],
    Purpose.opening: ["开市", "开业", "交易", "立券"],
    Purpose.wedding: ["嫁娶", "纳采", "订盟"],
}

PURPOSE_KEYWORDS_JI: dict[Purpose, list[str]] = {
    Purpose.move: ["入宅", "移徙"],
    Purpose.construction: ["动土", "修造"],
    Purpose.opening: ["开市", "交易"],
    Purpose.wedding: ["嫁娶"],
}


def _solar_of_day(d: date, tz: str) -> "Solar":
    # 以当地中午作为该日代表点，避免跨时区/夏令时边界对“日柱”的影响
    z = ZoneInfo(tz)
    dt = datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=z)
    return Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


def _extract_day_branch(solar: "Solar") -> str:
    lunar = solar.getLunar()
    # lunar-python 通常提供 getDayZhi()
    try:
        return lunar.getDayZhi()
    except Exception:
        gz = lunar.getDayInGanZhi()
        return gz[-1]


def _extract_month_branch(solar: "Solar") -> str:
    lunar = solar.getLunar()
    try:
        return lunar.getMonthZhi()
    except Exception:
        gz = lunar.getMonthInGanZhi()
        return gz[-1]


def _extract_year_branch(solar: "Solar") -> str:
    lunar = solar.getLunar()
    try:
        return lunar.getYearZhi()
    except Exception:
        gz = lunar.getYearInGanZhi()
        return gz[-1]


def _yi_ji(solar: "Solar") -> tuple[list[str], list[str]]:
    lunar = solar.getLunar()
    yi = []
    ji = []
    try:
        yi = list(lunar.getDayYi() or [])
    except Exception:
        yi = []
    try:
        ji = list(lunar.getDayJi() or [])
    except Exception:
        ji = []
    return yi, ji


JIANCHU_12 = ["建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭"]

# 简化的“十二建除”对目的偏好（可后续扩展为可配置）
JIANCHU_GOOD: dict[Purpose, set[str]] = {
    Purpose.move: {"成", "开", "定", "满"},
    Purpose.construction: {"成", "开", "定", "满", "建"},
    Purpose.opening: {"开", "成", "定", "满"},
    Purpose.wedding: {"成", "定", "开"},
}
JIANCHU_BAD: dict[Purpose, set[str]] = {
    Purpose.move: {"破", "闭", "危"},
    Purpose.construction: {"破", "闭", "危"},
    Purpose.opening: {"破", "闭", "危"},
    Purpose.wedding: {"破", "闭", "危"},
}


def _jianchu_12_of_day(solar: "Solar") -> str:
    """
    建除十二神算法（通行口径）：
    - 以“月支”为起点：当日地支与月支相同为“建”
    - 随日支序号递增依次轮转：建除满平定执破危成收开闭

    我们使用 lunar-python 的支序号，避免中文编码/字符差异影响。
    """
    lunar = solar.getLunar()
    try:
        m = lunar.getMonthZhiIndex()
        d = lunar.getDayZhiIndex()
    except Exception:
        # 兜底：用字符序
        order = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]
        m = order.index(lunar.getMonthZhi())
        d = order.index(lunar.getDayZhi())
    idx = (d - m) % 12
    return JIANCHU_12[idx]


def select_dates(req: DateSelectRequest) -> DateSelectResponse:
    person = req.person
    chart = build_bazi_chart(person)  # 保留：未来可把“喜忌”融入择日
    _ = chart

    if req.prefer_weekend and req.avoid_weekend:
        raise ValueError("prefer_weekend 与 avoid_weekend 不能同时为 True")

    zodiac = zodiac_from_birth(person)
    person_branch = ZODIAC_TO_BRANCH.get(zodiac)

    candidates: list[DateCandidate] = []

    if req.end is not None:
        if req.end < req.start:
            raise ValueError("end 不能早于 start")
        days = (req.end - req.start).days + 1
        if days > 366:
            raise ValueError("时间段过长（>366 天），请缩小范围或分段查询")
        end = req.end
    else:
        days = req.days
        end = req.start + timedelta(days=days - 1)

    exclude = set(req.exclude_dates or [])

    for i in range(days):
        d = req.start + timedelta(days=i)
        if d in exclude:
            continue
        solar = _solar_of_day(d, person.tz)
        day_branch = _extract_day_branch(solar)
        month_branch = _extract_month_branch(solar)
        year_branch = _extract_year_branch(solar)
        yi, ji = _yi_ji(solar)
        jianchu = _jianchu_12_of_day(solar)

        score = 50.0
        reasons: list[str] = []
        warnings: list[str] = []

        # 1) 冲生肖（六冲）
        if person_branch and BRANCH_CHONG.get(person_branch) == day_branch:
            score -= 35
            warnings.append(f"日支「{day_branch}」与命主生肖对应地支「{person_branch}」相冲（六冲），一般不优先。")

        # 2) 月破/岁破（简化规则：与月支/年支相冲者视为破）
        if BRANCH_CHONG.get(month_branch) == day_branch:
            score -= 25
            warnings.append(f"疑似月破：日支「{day_branch}」与月支「{month_branch}」相冲。")
        if BRANCH_CHONG.get(year_branch) == day_branch:
            score -= 20
            warnings.append(f"疑似岁破：日支「{day_branch}」与年支「{year_branch}」相冲。")

        # 3) 宜忌匹配（取通行黄历字段，做可解释评分）
        kw_yi = PURPOSE_KEYWORDS_YI.get(req.purpose, [])
        kw_ji = PURPOSE_KEYWORDS_JI.get(req.purpose, [])

        hit_yi = [k for k in kw_yi if any(k in x for x in yi)]
        hit_ji = [k for k in kw_ji if any(k in x for x in ji)]

        must_hit_yi = req.must_hit_yi
        if req.school in {DateSchool.strict}:
            must_hit_yi = True
        if must_hit_yi and not hit_yi:
            continue

        if req.school in {DateSchool.best_fit, DateSchool.almanac, DateSchool.strict}:
            if hit_yi:
                score += 22
                reasons.append(f"黄历“宜”命中：{ '、'.join(sorted(set(hit_yi))) }。")
            if hit_ji:
                score -= 32
                warnings.append(f"黄历“忌”命中：{ '、'.join(sorted(set(hit_ji))) }。")

        # 3.5) 建除十二神
        if req.school in {DateSchool.best_fit, DateSchool.jianchu, DateSchool.strict}:
            good_set = JIANCHU_GOOD.get(req.purpose, set())
            bad_set = JIANCHU_BAD.get(req.purpose, set())
            if jianchu in good_set:
                score += 14
                reasons.append(f"建除为「{jianchu}」，更偏吉用（匹配 {req.purpose.value}）。")
            elif jianchu in bad_set:
                score -= 20
                warnings.append(f"建除为「{jianchu}」，一般不优先（匹配 {req.purpose.value}）。")
            else:
                reasons.append(f"建除为「{jianchu}」。")

            if req.school is DateSchool.strict:
                # 严格模式：必须落在强吉集合
                if jianchu not in good_set:
                    continue

        # 4) 周末偏好
        is_weekend = d.weekday() >= 5
        if req.prefer_weekend and is_weekend:
            score += 6
            reasons.append("符合周末偏好。")
        if req.avoid_weekend and is_weekend:
            score -= 10
            warnings.append("你设置了避开周末。")

        # 5) 输出可解释信息
        if score >= 60:
            good_for = [req.purpose]
            bad_for: list[Purpose] = []
        elif score <= 35:
            good_for = []
            bad_for = [req.purpose]
        else:
            good_for = []
            bad_for = []

        candidates.append(
            DateCandidate(
                day=d,
                score=round(score, 2),
                good_for=good_for,
                bad_for=bad_for,
                reasons=reasons,
                warnings=warnings,
                raw={
                    "zodiac": zodiac,
                    "day_branch": day_branch,
                    "month_branch": month_branch,
                    "year_branch": year_branch,
                    "yi": yi,
                    "ji": ji,
                    "jianchu_12": jianchu,
                },
            )
        )

    # 排序与截断
    candidates = [c for c in candidates if c.score >= req.min_score]
    candidates_sorted = sorted(candidates, key=lambda c: c.score, reverse=True)
    top = candidates_sorted[: req.limit]
    return DateSelectResponse(
        purpose=req.purpose,
        start=req.start,
        end=end,
        days=days,
        candidates=top,
    )

