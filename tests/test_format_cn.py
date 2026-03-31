from __future__ import annotations

from datetime import date, datetime

from gosuan.bazi import build_bazi_chart
from gosuan.daily_fortune import daily_fortune
from gosuan.format_cn import (
    format_bazi_text,
    format_daily_fortune_text,
    format_divination_text,
    format_select_date_text,
    format_wealth_text,
)
from gosuan.meihua import meihua_divination
from gosuan.models import DailyFortuneRequest, DateSchool, Gender, PersonProfile, Purpose
from gosuan.wealth import _build_wealth_prompt, build_wealth_report


def _person() -> PersonProfile:
    return PersonProfile(
        name="测试",
        gender=Gender.male,
        birth_dt=datetime(1995, 8, 17, 14, 30, 0),
        tz="Asia/Shanghai",
    )


def test_format_bazi_text_contains_human_sections():
    person = _person()
    chart = build_bazi_chart(person)
    text = format_bazi_text(person.name, chart)
    assert "八字命盘" in text
    assert "四柱" in text
    assert person.name in text


def test_format_wealth_text_contains_sections():
    person = _person()
    report = build_wealth_report(person)
    text = format_wealth_text(person.name, report)
    assert "财运结构简报" in text
    assert "适合优先做的事" in text
    assert "需要特别留意" in text


def test_build_wealth_prompt_enforces_fixed_sections():
    person = _person()
    report = build_wealth_report(person)
    prompt = _build_wealth_prompt(person, report)
    assert "一、股票偏好" in prompt
    assert "二、彩票偏好" in prompt
    assert "三、财位处理" in prompt
    assert "四、今日忌讳" in prompt
    assert "只能输出上述四个一级标题" in prompt


def test_format_daily_fortune_text_contains_sections():
    person = _person()
    resp = daily_fortune(
        DailyFortuneRequest(person=person, day=date(2026, 4, 1), tz="Asia/Shanghai")
    )
    text = format_daily_fortune_text(person.name, resp)
    assert "个人运势" in text
    assert "今天更适合" in text
    assert "今天尽量避开" in text


def test_format_divination_text_contains_sections():
    person = _person()
    res = meihua_divination(
        person=person,
        question_dt=datetime(2026, 4, 1, 9, 30, 0),
        tz="Asia/Shanghai",
        personal_seed=True,
    )
    text = format_divination_text(person.name, res.to_dict())
    assert "起卦结果" in text
    assert "上卦" in text
    assert "动爻" in text


def test_format_select_date_text_empty_candidates():
    text = format_select_date_text(
        name="测试",
        purpose=Purpose.move,
        school=DateSchool.best_fit,
        payload={
            "开始日期": "2026-04-01",
            "结束日期": "2026-04-07",
            "候选日": [],
        },
    )
    assert "择日建议" in text
    assert "没有筛出合适日期" in text
