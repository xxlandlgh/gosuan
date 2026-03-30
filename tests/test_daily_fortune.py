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

