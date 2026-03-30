from __future__ import annotations

from datetime import datetime

from gosuan.meihua import meihua_divination
from gosuan.models import Gender, PersonProfile


def test_meihua_divination_deterministic():
    person = PersonProfile(
        name="测试",
        gender=Gender.male,
        birth_dt=datetime(1995, 8, 17, 14, 30, 0),
        tz="Asia/Shanghai",
    )
    q = datetime(2026, 4, 1, 9, 30, 0)
    r1 = meihua_divination(person=person, question_dt=q, tz="Asia/Shanghai", personal_seed=True)
    r2 = meihua_divination(person=person, question_dt=q, tz="Asia/Shanghai", personal_seed=True)
    assert r1.upper_index == r2.upper_index
    assert r1.lower_index == r2.lower_index
    assert r1.moving_line == r2.moving_line
    assert 1 <= r1.upper_index <= 8
    assert 1 <= r1.lower_index <= 8
    assert 1 <= r1.moving_line <= 6

