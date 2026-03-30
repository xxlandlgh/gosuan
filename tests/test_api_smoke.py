from __future__ import annotations

from datetime import date, datetime

from fastapi.testclient import TestClient

from gosuan.api import app


client = TestClient(app)


def test_home_page_ok_and_mobile_meta():
    r = client.get("/")
    assert r.status_code == 200
    assert "viewport" in r.text
    assert "gosuan" in r.text
    assert "通用初筛" in r.text


def test_health_ok():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ai_status_ok():
    r = client.get("/ai-status")
    assert r.status_code == 200
    data = r.json()
    assert "configured" in data
    assert "model" in data


def test_ai_probe_reports_failure_cleanly(monkeypatch):
    def fake_generate_ai_text(*, prompt, ai):
        raise ValueError("AI 服务鉴权失败（HTTP 403）。豆包/火山引擎返回拒绝。")

    monkeypatch.setattr("gosuan.openai_compat.generate_ai_text", fake_generate_ai_text)
    r = client.post("/ai-probe?model=test-model-not-real")
    assert r.status_code == 400
    assert "鉴权失败" in r.json()["detail"]


def test_bazi_ok():
    r = client.post(
        "/bazi",
        json={
            "name": "测试",
            "gender": "male",
            "birth_dt": "1995-08-17 14:30:00",
            "tz": "Asia/Shanghai",
            "location": None,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "day_master" in data


def test_bazi_pretty_cn_ok():
    r = client.post(
        "/bazi?pretty_cn=true",
        json={
            "name": "测试",
            "gender": "male",
            "birth_dt": "1995-08-17 14:30:00",
            "tz": "Asia/Shanghai",
            "location": None,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "八字命盘" in data["summary"]


def test_select_date_ok_range():
    r = client.post(
        "/select-date?pretty_cn=true",
        json={
            "person": {
                "name": "测试",
                "gender": "female",
                "birth_dt": "1990-01-01 09:00:00",
                "tz": "Asia/Shanghai",
                "location": None,
            },
            "purpose": "move",
            "school": "best_fit",
            "house_orientation": "坐北朝南",
            "door_orientation": "东南",
            "house_owner_name": "宅主张三",
            "house_owner_birth": "1988-06-18 08:30",
            "co_resident_notes": "夫妻二人同住",
            "move_time_window": "上午",
            "start": "2026-04-01",
            "end": "2026-04-10",
            "days": 60,
            "limit": 3,
            "prefer_weekend": False,
            "avoid_weekend": False,
            "exclude_dates": [],
            "must_hit_yi": False,
            "min_score": 0,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["开始日期"] == "2026-04-01"
    assert data["结束日期"] == "2026-04-10"
    assert len(data["补充条件"]) >= 3
    assert len(data["候选日"]) == 3


def test_divine_ok():
    r = client.post(
        "/divine",
        json={
            "person": {
                "name": "测试",
                "gender": "male",
                "birth_dt": "1995-08-17 14:30:00",
                "tz": "Asia/Shanghai",
                "location": None,
            },
            "question_time": "2026-04-01 09:30:00",
            "tz": "Asia/Shanghai",
            "personal_seed": True,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert 1 <= int(data["moving_line"]) <= 6


def test_daily_fortune_ok():
    r = client.post(
        "/daily-fortune",
        json={
            "person": {
                "name": "测试",
                "gender": "male",
                "birth_dt": "1995-08-17 14:30:00",
                "tz": "Asia/Shanghai",
                "location": None,
            },
            "day": "2026-04-01",
            "tz": "Asia/Shanghai",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["day"] == "2026-04-01"
    assert "good" in data and isinstance(data["good"], list)
    assert "bad" in data and isinstance(data["bad"], list)


def test_daily_fortune_pretty_cn_ok():
    r = client.post(
        "/daily-fortune?pretty_cn=true",
        json={
            "person": {
                "name": "测试",
                "gender": "male",
                "birth_dt": "1995-08-17 14:30:00",
                "tz": "Asia/Shanghai",
                "location": None,
            },
            "day": "2026-04-01",
            "tz": "Asia/Shanghai",
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "个人运势" in data["summary"]

