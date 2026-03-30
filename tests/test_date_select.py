from __future__ import annotations

from datetime import date, datetime

from gosuan.date_select import select_dates
from gosuan.models import DateSchool, DateSelectRequest, Gender, PersonProfile, Purpose


def test_select_dates_returns_candidates_sorted():
    person = PersonProfile(
        name="测试",
        gender=Gender.female,
        birth_dt=datetime(1990, 1, 1, 9, 0, 0),
        tz="Asia/Shanghai",
    )
    req = DateSelectRequest(
        person=person,
        purpose=Purpose.move,
        school=DateSchool.best_fit,
        start=date(2026, 4, 1),
        end=date(2026, 4, 20),
        days=20,
        limit=5,
        prefer_weekend=False,
        avoid_weekend=False,
    )
    resp = select_dates(req)
    assert resp.purpose == Purpose.move
    assert resp.start == date(2026, 4, 1)
    assert resp.end == date(2026, 4, 20)
    assert len(resp.candidates) == 5
    scores = [c.score for c in resp.candidates]
    assert scores == sorted(scores, reverse=True)

