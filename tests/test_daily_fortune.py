from __future__ import annotations

from datetime import date, datetime

from gosuan.daily_fortune import daily_fortune
from gosuan.models import DailyFortuneRequest, Gender, PersonProfile


def test_daily_fortune_basic_fields():
    person = PersonProfile(
        name="测试",
        gender=Gender.female,
        birth_dt=datetime(1990, 1, 1, 9, 0, 0),
        tz="Asia/Shanghai",
    )
    req = DailyFortuneRequest(person=person, day=date(2026, 4, 1), tz="Asia/Shanghai")
    resp = daily_fortune(req)
    assert resp.day == date(2026, 4, 1)
    # 终端/日志编码可能导致展示乱码，这里只验证“确实是一个生肖字符”
    assert isinstance(resp.zodiac, str)
    assert len(resp.zodiac) == 1
    assert isinstance(resp.yi, list)
    assert isinstance(resp.ji, list)
    assert isinstance(resp.good, list)
    assert isinstance(resp.bad, list)
    assert isinstance(resp.lucky_numbers, list)
    assert len(resp.lucky_numbers) == 3
    assert isinstance(resp.lottery_numbers, list)
    assert len(resp.lottery_numbers) == 6
    assert isinstance(resp.lottery_recommendations, dict)
    assert "双色球红球" in resp.lottery_recommendations
    assert "大乐透前区" in resp.lottery_recommendations
    assert resp.stock_market_level in {"偏保守", "偏观望", "偏确认"}
    assert isinstance(resp.stock_preferred_digits, list)
    assert isinstance(resp.stock_avoid_digits, list)
    assert isinstance(resp.stock_theme_keywords, list)
    assert isinstance(resp.stock_avoid_keywords, list)
    assert isinstance(resp.stock_code_hints, list)
    assert isinstance(resp.stock_market_note, str)

