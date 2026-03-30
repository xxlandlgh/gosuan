from __future__ import annotations

from datetime import datetime

from gosuan.bazi import build_bazi_chart
from gosuan.models import Gender, PersonProfile


def test_build_bazi_chart_basic_fields():
    person = PersonProfile(
        name="测试",
        gender=Gender.male,
        birth_dt=datetime(1995, 8, 17, 14, 30, 0),
        tz="Asia/Shanghai",
    )
    chart = build_bazi_chart(person)
    assert chart.day_master in {"甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"}
    assert chart.year.stem and chart.year.branch
    assert chart.month.stem and chart.month.branch
    assert chart.day.stem and chart.day.branch
    assert chart.hour.stem and chart.hour.branch
    assert set(chart.wuxing_counts.keys()) == {"木", "火", "土", "金", "水"}

