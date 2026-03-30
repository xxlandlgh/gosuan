from __future__ import annotations

from datetime import date, datetime

import pytest

from gosuan.date_select import select_dates
from gosuan.models import DateSchool, DateSelectRequest, Gender, PersonProfile, Purpose


def _person() -> PersonProfile:
    return PersonProfile(
        name="测试",
        gender=Gender.male,
        birth_dt=datetime(1995, 8, 17, 14, 30, 0),
        tz="Asia/Shanghai",
    )


def test_prefer_and_avoid_weekend_conflict():
    req = DateSelectRequest(
        person=_person(),
        purpose=Purpose.move,
        start=date(2026, 4, 1),
        days=10,
        limit=3,
        prefer_weekend=True,
        avoid_weekend=True,
    )
    with pytest.raises(ValueError):
        select_dates(req)


def test_exclude_dates_removes_day():
    req = DateSelectRequest(
        person=_person(),
        purpose=Purpose.move,
        school=DateSchool.best_fit,
        start=date(2026, 4, 1),
        end=date(2026, 4, 5),
        limit=10,
        exclude_dates=[date(2026, 4, 2), date(2026, 4, 3)],
    )
    resp = select_dates(req)
    days = {c.day for c in resp.candidates}
    assert date(2026, 4, 2) not in days
    assert date(2026, 4, 3) not in days

