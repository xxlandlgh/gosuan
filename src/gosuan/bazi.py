from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from lunar_python import Solar  # type: ignore

from .models import BaziChart, BaziPillar, PersonProfile


STEM_INFO: dict[str, tuple[str, str]] = {
    "甲": ("木", "阳"),
    "乙": ("木", "阴"),
    "丙": ("火", "阳"),
    "丁": ("火", "阴"),
    "戊": ("土", "阳"),
    "己": ("土", "阴"),
    "庚": ("金", "阳"),
    "辛": ("金", "阴"),
    "壬": ("水", "阳"),
    "癸": ("水", "阴"),
}

# 地支主气五行（用于粗略统计；更精细可用藏干）
BRANCH_MAIN_ELEMENT: dict[str, str] = {
    "子": "水",
    "丑": "土",
    "寅": "木",
    "卯": "木",
    "辰": "土",
    "巳": "火",
    "午": "火",
    "未": "土",
    "申": "金",
    "酉": "金",
    "戌": "土",
    "亥": "水",
}

# 藏干（常用表；用于更接近“旺衰结构”的五行统计）
BRANCH_HIDDEN_STEMS: dict[str, list[str]] = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}

GENERATES = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
CONTROLS = {"木": "土", "火": "金", "土": "水", "金": "木", "水": "火"}


def _pillar_from_ganzhi(gz: str) -> BaziPillar:
    if len(gz) != 2:
        raise ValueError(f"无法解析干支：{gz!r}")
    return BaziPillar(stem=gz[0], branch=gz[1])


def _ten_god(day_master: str, other_stem: str) -> str:
    dm_el, dm_yy = STEM_INFO[day_master]
    ot_el, ot_yy = STEM_INFO[other_stem]

    same_polar = dm_yy == ot_yy

    if ot_el == dm_el:
        return "比肩" if same_polar else "劫财"

    if GENERATES[dm_el] == ot_el:
        return "食神" if same_polar else "伤官"

    if CONTROLS[dm_el] == ot_el:
        # 我克者为财：同阴阳偏财，异阴阳正财（常用口径）
        return "偏财" if same_polar else "正财"

    if CONTROLS[ot_el] == dm_el:
        # 克我者为官杀：同阴阳七杀，异阴阳正官（常用口径）
        return "七杀" if same_polar else "正官"

    if GENERATES[ot_el] == dm_el:
        return "偏印" if same_polar else "正印"

    return "未知"


def _count_wuxing(pillars: list[BaziPillar]) -> dict[str, int]:
    counts = {k: 0 for k in ["木", "火", "土", "金", "水"]}
    for p in pillars:
        el, _ = STEM_INFO[p.stem]
        counts[el] += 2  # 天干权重略高，便于“结构”解读
        counts[BRANCH_MAIN_ELEMENT[p.branch]] += 1
        for hs in BRANCH_HIDDEN_STEMS.get(p.branch, []):
            hel, _ = STEM_INFO[hs]
            counts[hel] += 1
    return counts


def build_bazi_chart(person: PersonProfile) -> BaziChart:
    """
    生成八字命盘（可解释结构）。

    - 使用 `lunar-python` 的四柱换算，避免手写历法易错点
    - `birth_dt` 按 `tz` 转为当地时间后再排盘
    """
    tz = ZoneInfo(person.tz)
    dt_local = person.birth_dt
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=tz)
    else:
        dt_local = dt_local.astimezone(tz)

    solar = Solar.fromYmdHms(
        dt_local.year, dt_local.month, dt_local.day, dt_local.hour, dt_local.minute, dt_local.second
    )
    lunar = solar.getLunar()
    eight = lunar.getEightChar()

    year = _pillar_from_ganzhi(eight.getYear())
    month = _pillar_from_ganzhi(eight.getMonth())
    day = _pillar_from_ganzhi(eight.getDay())
    hour = _pillar_from_ganzhi(eight.getTime())

    pillars = [year, month, day, hour]
    dm = day.stem

    shishen = {
        "year_stem": _ten_god(dm, year.stem),
        "month_stem": _ten_god(dm, month.stem),
        "hour_stem": _ten_god(dm, hour.stem),
    }
    wuxing_counts = _count_wuxing(pillars)

    raw = {
        "solar": {
            "ymdhms": dt_local.strftime("%Y-%m-%d %H:%M:%S"),
            "tz": person.tz,
        },
        "lunar": {
            "ymd": f"{lunar.getYear()}-{lunar.getMonth()}-{lunar.getDay()}",
            "animal": getattr(lunar, "getYearShengXiao", lunar.getAnimal)(),
        },
        "eight_char": {
            "year": eight.getYear(),
            "month": eight.getMonth(),
            "day": eight.getDay(),
            "time": eight.getTime(),
            "day_gan": eight.getDayGan(),
            "day_zhi": eight.getDayZhi(),
        },
    }

    return BaziChart(
        year=year,
        month=month,
        day=day,
        hour=hour,
        day_master=dm,
        wuxing_counts=wuxing_counts,
        shishen=shishen,
        raw=raw,
    )


def zodiac_from_birth(person: PersonProfile) -> str:
    tz = ZoneInfo(person.tz)
    dt_local = person.birth_dt
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=tz)
    else:
        dt_local = dt_local.astimezone(tz)

    solar = Solar.fromYmdHms(dt_local.year, dt_local.month, dt_local.day, 12, 0, 0)
    lunar = solar.getLunar()
    return getattr(lunar, "getYearShengXiao", lunar.getAnimal)()

