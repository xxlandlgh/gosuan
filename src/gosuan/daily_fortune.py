from __future__ import annotations

import hashlib
import random
from datetime import date, datetime
from zoneinfo import ZoneInfo

from lunar_python import Solar  # type: ignore

from .bazi import zodiac_from_birth
from .date_select import BRANCH_CHONG, ZODIAC_TO_BRANCH
from .models import DailyFortuneRequest, DailyFortuneResponse


JIANCHU_12 = ["建", "除", "满", "平", "定", "执", "破", "危", "成", "收", "开", "闭"]


def _safe_call(obj, name: str, default=None):
    try:
        fn = getattr(obj, name)
    except Exception:
        return default
    try:
        return fn()
    except Exception:
        return default


def _solar_of_day(d: date, tz: str) -> "Solar":
    z = ZoneInfo(tz)
    dt = datetime(d.year, d.month, d.day, 12, 0, 0, tzinfo=z)
    return Solar.fromYmdHms(dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)


def _jianchu_12_of_day(solar: "Solar") -> str:
    lunar = solar.getLunar()
    try:
        m = lunar.getMonthZhiIndex()
        di = lunar.getDayZhiIndex()
        idx = (di - m) % 12
        return JIANCHU_12[idx]
    except Exception:
        return "未知"


def _today_in_tz(tz: str) -> date:
    z = ZoneInfo(tz)
    return datetime.now(tz=z).date()


def _stable_rng_seed(*parts: str) -> int:
    text = "|".join(parts)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(digest[:16], 16)


def _daily_entertainment_numbers(
    *, person_name: str, birth_dt: datetime, day: date
) -> tuple[list[int], list[int], dict[str, list[int]]]:
    seed = _stable_rng_seed(person_name, birth_dt.isoformat(), day.isoformat())
    rng = random.Random(seed)
    lucky_numbers = sorted(rng.sample(list(range(1, 10)), 3))
    lottery_numbers = sorted(rng.sample(list(range(1, 34)), 6))
    lottery_recommendations = {
        "双色球红球": sorted(rng.sample(list(range(1, 34)), 6)),
        "双色球蓝球": sorted(rng.sample(list(range(1, 17)), 1)),
        "大乐透前区": sorted(rng.sample(list(range(1, 36)), 5)),
        "大乐透后区": sorted(rng.sample(list(range(1, 13)), 2)),
    }
    return lucky_numbers, lottery_numbers, lottery_recommendations


def _stock_market_outlook(
    *, chong_person: bool, jianchu: str, yi: list[str], ji: list[str]
) -> tuple[str, str]:
    if chong_person or jianchu in {"破", "危", "闭"} or any("交易" in x or "开市" in x for x in ji):
        level = "偏保守"
    elif jianchu in {"成", "开", "定"} and any("交易" in x or "立券" in x or "开市" in x for x in yi):
        level = "偏确认"
    else:
        level = "偏观望"

    notes: list[str] = []
    if chong_person:
        notes.append("今天更适合观察和等待，不适合按情绪追涨杀跌。")
    else:
        notes.append("今天适合先做计划和复盘，再决定是否继续跟踪市场。")
    if jianchu in {"成", "开", "定"}:
        notes.append("从节奏上看，偏向确认信号、分批观察，而不是重仓判断。")
    elif jianchu in {"破", "危", "闭"}:
        notes.append("从节奏上看，偏向控制风险，避免把短线波动误判成确定机会。")
    if any("交易" in x or "立券" in x or "开市" in x for x in yi):
        notes.append("黄历层面有交易相关字样，但这不构成真实买卖建议。")
    if any("交易" in x or "开市" in x for x in ji):
        notes.append("黄历层面有交易忌项，今天更适合缩小仓位、减少冲动。")
    notes.append("仅作娱乐化市场观察，不构成股票买入建议。")
    return level, "".join(notes[:4])


def _stock_focus(
    *,
    person_name: str,
    birth_dt: datetime,
    day: date,
    lucky_numbers: list[int],
    chong_person: bool,
    jianchu: str,
) -> tuple[list[int], list[int], list[str], list[str], list[str]]:
    seed = _stable_rng_seed("stock-focus", person_name, birth_dt.isoformat(), day.isoformat(), jianchu)
    rng = random.Random(seed)
    digits = list(range(10))
    preferred_digits = sorted(set(lucky_numbers + rng.sample(digits, 2)))[:4]
    avoid_pool = [x for x in digits if x not in preferred_digits]
    avoid_digits = sorted(rng.sample(avoid_pool, 3))

    if chong_person or jianchu in {"破", "危", "闭"}:
        preferred_themes_pool = ["高股息", "公用事业", "消费龙头", "央国企", "防御板块"]
        avoid_themes_pool = ["高波动题材", "连板炒作", "纯概念小票", "高杠杆品种", "追涨热点"]
    elif jianchu in {"成", "开", "定"}:
        preferred_themes_pool = ["业绩兑现", "现金流稳健", "景气上行", "趋势确认", "龙头板块"]
        avoid_themes_pool = ["情绪退潮", "无量拉升", "题材末端", "高位博弈", "消息兑现后回落"]
    else:
        preferred_themes_pool = ["业绩预增", "估值修复", "低位放量", "行业龙头", "顺周期"]
        avoid_themes_pool = ["高位分歧", "壳概念", "单日异动", "题材轮动末端", "短线透支"]

    preferred_themes = rng.sample(preferred_themes_pool, 3)
    avoid_themes = rng.sample(avoid_themes_pool, 3)
    code_hints = [
        f"可优先留意代码中含 {preferred_digits[0]}、{preferred_digits[1]} 的标的",
        f"若必须二选一，可先避开尾号带 {avoid_digits[0]}、{avoid_digits[1]} 的标的",
        f"更适合看代码结构清晰、重复数字较少的标的；少碰连续同尾号过多的票",
    ]
    return preferred_digits, avoid_digits, preferred_themes, avoid_themes, code_hints


def _personalize_good_bad(
    *,
    yi: list[str],
    ji: list[str],
    chong_person: bool,
    jianchu: str,
) -> tuple[list[str], list[str], list[str]]:
    notes: list[str] = []
    good: list[str] = []
    bad: list[str] = []

    # 1) 直接取黄历宜忌作为基底（但转成更“可执行”的表达）
    if yi:
        good.extend([f"适合：{x}" for x in yi[:8]])
    if ji:
        bad.extend([f"尽量避开：{x}" for x in ji[:8]])

    # 2) 冲日时做“个人化”约束（偏保守，避免误导）
    if chong_person:
        notes.append("今日与命主生肖六冲，宜“稳守少折腾”：重要签约/搬迁/大额决策尽量避开或多做备选。")
        bad.extend(
            [
                "尽量避开：搬迁/入宅/安床等大动作（若必须做，建议仅做准备与流程性事项）",
                "尽量避开：情绪化沟通、硬碰硬谈判",
            ]
        )
        good.extend(
            [
                "适合：整理/复盘/做备选方案（把风险点写清）",
                "适合：低风险推进（按流程走、少临场改动）",
            ]
        )

    # 3) 建除十二神的结构性提示
    if jianchu in {"破", "危", "闭"}:
        notes.append(f"建除为「{jianchu}」，通常不优先用于开新局/开工/搬家等“启动型”事项。")
        bad.append("尽量避开：启动新项目/重大开工/大规模改造（更适合收尾与风险处理）")
    elif jianchu in {"成", "开", "定"}:
        notes.append(f"建除为「{jianchu}」，更利于“定下来/推进落地/开门见客”的事项。")
        good.append("适合：推动关键节点落地（把事项做成可交付）")

    # 去重并保持顺序
    def uniq(xs: list[str]) -> list[str]:
        seen = set()
        out = []
        for x in xs:
            if x not in seen:
                out.append(x)
                seen.add(x)
        return out

    return uniq(good)[:12], uniq(bad)[:12], notes


def daily_fortune(req: DailyFortuneRequest) -> DailyFortuneResponse:
    person = req.person
    tz = req.tz or person.tz
    d = req.day or _today_in_tz(tz)
    solar = _solar_of_day(d, tz)
    lunar = solar.getLunar()

    yi = list(_safe_call(lunar, "getDayYi", []) or [])
    ji = list(_safe_call(lunar, "getDayJi", []) or [])
    day_gz = _safe_call(lunar, "getDayInGanZhi", "") or ""
    day_zhi = _safe_call(lunar, "getDayZhi", None)
    jianchu = _jianchu_12_of_day(solar)

    # 与个人生肖关系
    zodiac = zodiac_from_birth(person)
    person_branch = ZODIAC_TO_BRANCH.get(zodiac)
    chong_person = bool(person_branch and day_zhi and BRANCH_CHONG.get(person_branch) == day_zhi)

    day_chong_zodiac = _safe_call(lunar, "getDayChongShengXiao", None)
    day_sha = _safe_call(lunar, "getDaySha", None)
    xiong_sha = _safe_call(lunar, "getDayXiongSha", None)
    ji_shen = _safe_call(lunar, "getDayJiShen", None)
    tian_shen = _safe_call(lunar, "getDayTianShen", None)
    tian_shen_luck = _safe_call(lunar, "getDayTianShenLuck", None)

    # 方位：用“喜神/财神/福神/太岁”做“适合去/不适合去”的解释性输出
    pos_xi = _safe_call(lunar, "getDayPositionXiDesc", None) or _safe_call(lunar, "getDayPositionXi", None)
    pos_cai = _safe_call(lunar, "getDayPositionCaiDesc", None) or _safe_call(lunar, "getDayPositionCai", None)
    pos_fu = _safe_call(lunar, "getDayPositionFuDesc", None) or _safe_call(lunar, "getDayPositionFu", None)
    pos_taisui = _safe_call(lunar, "getDayPositionTaiSuiDesc", None) or _safe_call(lunar, "getDayPositionTaiSui", None)

    go_directions = [x for x in [pos_xi, pos_cai, pos_fu] if x]
    avoid_directions = [x for x in [pos_taisui] if x]
    lucky_direction = go_directions[0] if go_directions else None
    lucky_numbers, lottery_numbers, lottery_recommendations = _daily_entertainment_numbers(
        person_name=person.name,
        birth_dt=person.birth_dt,
        day=d,
    )
    stock_market_level, stock_market_note = _stock_market_outlook(
        chong_person=chong_person,
        jianchu=jianchu,
        yi=yi,
        ji=ji,
    )
    (
        stock_preferred_digits,
        stock_avoid_digits,
        stock_theme_keywords,
        stock_avoid_keywords,
        stock_code_hints,
    ) = _stock_focus(
        person_name=person.name,
        birth_dt=person.birth_dt,
        day=d,
        lucky_numbers=lucky_numbers,
        chong_person=chong_person,
        jianchu=jianchu,
    )

    good, bad, notes = _personalize_good_bad(
        yi=yi,
        ji=ji,
        chong_person=chong_person,
        jianchu=jianchu,
    )

    if day_sha:
        notes.append(f"冲煞提示：{day_sha}。")
    if xiong_sha:
        notes.append(f"凶煞：{xiong_sha}。")
    if ji_shen:
        notes.append(f"吉神：{ji_shen}。")
    if tian_shen and tian_shen_luck:
        notes.append(f"值神：{tian_shen}（{tian_shen_luck}）。")

    raw = {
        "yi": yi,
        "ji": ji,
        "jianchu_12": jianchu,
        "day_ganzhi": day_gz,
        "day_zhi": day_zhi,
        "day_chong_zodiac": day_chong_zodiac,
        "day_sha": day_sha,
        "day_xiong_sha": xiong_sha,
        "day_ji_shen": ji_shen,
        "day_tian_shen": tian_shen,
        "day_tian_shen_luck": tian_shen_luck,
        "pos_xi": pos_xi,
        "pos_cai": pos_cai,
        "pos_fu": pos_fu,
        "pos_taisui": pos_taisui,
        "lucky_numbers": lucky_numbers,
        "lottery_numbers": lottery_numbers,
        "lottery_recommendations": lottery_recommendations,
        "lucky_direction": lucky_direction,
        "stock_market_level": stock_market_level,
        "stock_preferred_digits": stock_preferred_digits,
        "stock_avoid_digits": stock_avoid_digits,
        "stock_theme_keywords": stock_theme_keywords,
        "stock_avoid_keywords": stock_avoid_keywords,
        "stock_code_hints": stock_code_hints,
        "stock_market_note": stock_market_note,
    }

    return DailyFortuneResponse(
        day=d,
        tz=tz,
        zodiac=zodiac,
        day_ganzhi=day_gz,
        day_chong_zodiac=day_chong_zodiac,
        jianchu_12=jianchu,
        yi=yi,
        ji=ji,
        good=good,
        bad=bad,
        go_directions=go_directions,
        avoid_directions=avoid_directions,
        lucky_numbers=lucky_numbers,
        lucky_direction=lucky_direction,
        lottery_numbers=lottery_numbers,
        lottery_recommendations=lottery_recommendations,
        stock_market_level=stock_market_level,
        stock_preferred_digits=stock_preferred_digits,
        stock_avoid_digits=stock_avoid_digits,
        stock_theme_keywords=stock_theme_keywords,
        stock_avoid_keywords=stock_avoid_keywords,
        stock_code_hints=stock_code_hints,
        stock_market_note=stock_market_note,
        notes=notes,
        raw=raw,
    )

