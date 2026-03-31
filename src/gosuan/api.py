from __future__ import annotations

import os
from collections import defaultdict
from datetime import date, datetime
from threading import Lock

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse

from .bazi import build_bazi_chart
from .daily_fortune import daily_fortune
from .date_select import select_dates
from .format_cn import (
    format_bazi_text,
    format_daily_fortune_text,
    format_divination_text,
    format_wealth_text,
    purpose_cn,
    school_cn,
    summarize_candidate,
    weekday_cn,
)
from .meihua import meihua_divination
from .models import (
    AiConfig,
    DailyFortuneRequest,
    DateSelectRequest,
    DivineRequest,
    PersonProfile,
)
from .openai_compat import ai_config_from_env
from .wealth import build_wealth_report


app = FastAPI(title="gosuan", version="0.1.0")
AI_RATE_LIMIT_PER_HOUR = 5
_AI_USAGE_LOCK = Lock()
_AI_USAGE_COUNTERS: dict[str, int] = defaultdict(int)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _ai_subject_key(request: Request, person: PersonProfile | None = None) -> str:
    ip = _client_ip(request)
    if person:
        return f"{person.name.strip()}|{person.birth_dt.isoformat()}|{ip}"
    return f"anonymous|{ip}"


def _consume_ai_quota(request: Request, person: PersonProfile | None = None) -> None:
    hour_bucket = datetime.now().strftime("%Y-%m-%d-%H")
    subject = _ai_subject_key(request, person)
    counter_key = f"{hour_bucket}|{subject}"
    with _AI_USAGE_LOCK:
        current = _AI_USAGE_COUNTERS.get(counter_key, 0)
        if current >= AI_RATE_LIMIT_PER_HOUR:
            raise HTTPException(
                status_code=429,
                detail=f"当前账号 1 小时内 AI 调用次数已用完（{AI_RATE_LIMIT_PER_HOUR}/{AI_RATE_LIMIT_PER_HOUR}），请稍后再试。",
            )
        _AI_USAGE_COUNTERS[counter_key] = current + 1


@app.get("/", response_class=HTMLResponse)
def home():
    # 轻量纯前端页面：同域 fetch 调用后端接口，便于手机端使用（无需额外前端工程/依赖）。
    html = """
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <title>gosuan - 个人算命/财运/择日/算卦/今日运势</title>
    <style>
      :root {
        --bg: #07111f;
        --bg-soft: #0f1d33;
        --card: rgba(10, 25, 48, 0.72);
        --card-strong: rgba(13, 31, 58, 0.92);
        --card-glow: rgba(116, 214, 164, 0.12);
        --text: rgba(245, 248, 255, 0.95);
        --muted: rgba(206, 220, 240, 0.72);
        --border: rgba(172, 210, 240, 0.14);
        --accent: #74d6a4;
        --accent-2: #f3c969;
        --danger: #ff8c8c;
        --shadow: 0 20px 60px rgba(0, 0, 0, 0.28);
      }
      * { box-sizing: border-box; }
      html, body { height: 100%; }
      body {
        margin: 0;
        background:
          radial-gradient(1000px 580px at 12% 10%, rgba(116,214,164,0.16), transparent 58%),
          radial-gradient(980px 620px at 86% 18%, rgba(243,201,105,0.10), transparent 58%),
          radial-gradient(720px 540px at 50% 100%, rgba(67,136,255,0.12), transparent 60%),
          linear-gradient(180deg, #07111f 0%, #09192b 42%, #06101d 100%);
        color: var(--text);
        font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
        position: relative;
      }
      body::before {
        content: "";
        position: fixed;
        inset: 0;
        pointer-events: none;
        background-image:
          linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px),
          linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px);
        background-size: 28px 28px;
        mask-image: linear-gradient(180deg, rgba(0,0,0,0.65), transparent 88%);
      }
      a { color: #b9f3d8; text-decoration: none; }
      .wrap { max-width: 1180px; margin: 0 auto; padding: 22px 18px 72px; position: relative; z-index: 1; }
      .topbar { display: flex; justify-content: space-between; align-items: center; gap: 14px; }
      .brand { font-size: 28px; font-weight: 900; letter-spacing: 0.08em; text-transform: uppercase; }
      .sub { color: var(--muted); font-size: 13px; margin-top: 8px; max-width: 720px; }
      .hero {
        margin-top: 18px;
        padding: 26px;
        border-radius: 28px;
        background:
          linear-gradient(145deg, rgba(9, 26, 49, 0.9), rgba(12, 34, 62, 0.82)),
          radial-gradient(circle at top right, rgba(116,214,164,0.18), transparent 36%);
        border: 1px solid rgba(194, 231, 255, 0.14);
        box-shadow: var(--shadow);
        overflow: hidden;
      }
      .hero-grid { display: grid; gap: 20px; grid-template-columns: 1fr; }
      @media (min-width: 920px) { .hero-grid { grid-template-columns: 1.3fr 0.9fr; } }
      .eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 8px 14px;
        border-radius: 999px;
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.10);
        color: var(--muted);
        font-size: 12px;
      }
      .hero h1 {
        margin: 16px 0 12px;
        font-size: clamp(32px, 6vw, 56px);
        line-height: 1.05;
        letter-spacing: 0.02em;
      }
      .hero p {
        margin: 0;
        color: var(--muted);
        font-size: 15px;
        line-height: 1.8;
        max-width: 720px;
      }
      .hero-stats { display: grid; gap: 12px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin-top: 22px; }
      .stat {
        padding: 16px;
        border-radius: 18px;
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.08);
      }
      .stat b { display: block; font-size: 24px; margin-bottom: 6px; color: #fff4d8; }
      .stat span { color: var(--muted); font-size: 12px; line-height: 1.6; }
      .hero-panel {
        padding: 18px;
        border-radius: 22px;
        background: linear-gradient(180deg, rgba(255,255,255,0.07), rgba(255,255,255,0.03));
        border: 1px solid rgba(255,255,255,0.10);
        box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
      }
      .hero-panel h3 { margin: 0 0 12px; font-size: 14px; letter-spacing: 0.06em; color: #fff4d8; }
      .feature-list { display: grid; gap: 10px; }
      .feature-item {
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(255,255,255,0.045);
        border: 1px solid rgba(255,255,255,0.08);
      }
      .feature-item strong { display: block; margin-bottom: 6px; font-size: 14px; }
      .feature-item span { color: var(--muted); font-size: 12px; line-height: 1.7; }
      .section-head {
        display: flex;
        justify-content: space-between;
        align-items: end;
        gap: 16px;
        margin: 26px 2px 14px;
      }
      .section-head h2 { margin: 0; font-size: 24px; }
      .section-head p { margin: 0; color: var(--muted); font-size: 13px; max-width: 580px; line-height: 1.7; }
      .grid { display: grid; grid-template-columns: 1fr; gap: 16px; margin-top: 12px; }
      @media (min-width: 900px) { .grid { grid-template-columns: 1fr 1fr; } }
      .card {
        position: relative;
        background:
          linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.015)),
          var(--card);
        border: 1px solid var(--border);
        border-radius: 24px;
        padding: 18px;
        backdrop-filter: blur(16px);
        box-shadow: var(--shadow);
        overflow: hidden;
      }
      .card::after {
        content: "";
        position: absolute;
        inset: auto -20% -55% 40%;
        height: 160px;
        background: radial-gradient(circle, var(--card-glow), transparent 62%);
        pointer-events: none;
      }
      .card h2 { margin: 0 0 6px; font-size: 18px; }
      .card-lead { color: var(--muted); font-size: 12px; line-height: 1.7; margin-bottom: 14px; }
      .row { display: grid; grid-template-columns: 1fr; gap: 12px; }
      @media (min-width: 640px) { .row.two { grid-template-columns: 1fr 1fr; } }
      label { display: block; font-size: 12px; color: var(--muted); margin-bottom: 7px; letter-spacing: 0.02em; }
      input, select, textarea {
        width: 100%;
        background: rgba(255,255,255,0.055);
        border: 1px solid rgba(255,255,255,0.10);
        color: var(--text);
        border-radius: 16px;
        padding: 13px 14px;
        outline: none;
        font-size: 14px;
        transition: border-color 160ms ease, transform 160ms ease, background 160ms ease, box-shadow 160ms ease;
      }
      input:focus, select:focus, textarea:focus {
        border-color: rgba(116,214,164,0.55);
        background: rgba(255,255,255,0.08);
        box-shadow: 0 0 0 4px rgba(116,214,164,0.10);
        transform: translateY(-1px);
      }
      select, option, optgroup {
        background-color: #27364c;
        color: #eef4ff;
      }
      textarea { min-height: 112px; resize: vertical; }
      .btns { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
      button {
        appearance: none;
        border: 1px solid rgba(255,255,255,0.12);
        background: linear-gradient(135deg, rgba(116,214,164,0.26), rgba(116,214,164,0.12));
        color: #eefcf6;
        border-radius: 999px;
        padding: 11px 16px;
        font-weight: 700;
        cursor: pointer;
        transition: transform 180ms ease, box-shadow 180ms ease, border-color 180ms ease, background 180ms ease;
      }
      button:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 22px rgba(0,0,0,0.18);
        border-color: rgba(116,214,164,0.34);
      }
      button.secondary {
        background: rgba(255,255,255,0.06);
        color: var(--text);
      }
      button.danger { background: rgba(251,113,133,0.16); }
      .hint { color: var(--muted); font-size: 12px; line-height: 1.7; margin-top: 12px; }
      .out {
        margin-top: 14px;
        background: linear-gradient(180deg, rgba(4,13,24,0.55), rgba(255,255,255,0.03));
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 18px;
        padding: 14px;
        white-space: pre-wrap;
        word-break: break-word;
        font-family: "Microsoft YaHei", "PingFang SC", "Noto Sans CJK SC", sans-serif;
        font-size: 13px;
        line-height: 1.7;
        color: rgba(255,255,255,0.86);
        min-height: 120px;
        max-height: 420px;
        overflow: auto;
      }
      .out.is-loading {
        position: relative;
        overflow: hidden;
      }
      .out.is-loading::after {
        content: "";
        position: absolute;
        inset: 0;
        background: linear-gradient(90deg, transparent, rgba(255,255,255,0.08), transparent);
        transform: translateX(-100%);
        animation: shimmer 1.2s infinite;
      }
      .loading-box {
        display: grid;
        gap: 10px;
        align-content: center;
        min-height: 120px;
        color: var(--muted);
      }
      .loading-dotline {
        display: inline-flex;
        gap: 6px;
        align-items: center;
      }
      .loading-dot {
        width: 8px;
        height: 8px;
        border-radius: 999px;
        background: rgba(116,214,164,0.85);
        animation: pulse 1s infinite ease-in-out;
      }
      .loading-dot:nth-child(2) { animation-delay: 0.15s; }
      .loading-dot:nth-child(3) { animation-delay: 0.3s; }
      .result-title { font-size: 18px; font-weight: 800; margin-bottom: 8px; color: #fff8e5; }
      .result-block { margin-top: 10px; padding: 12px 14px; border-radius: 16px; background: rgba(255,255,255,0.045); border: 1px solid rgba(255,255,255,0.08); }
      .result-line { margin: 6px 0; }
      .result-bullet { display: flex; gap: 8px; margin: 6px 0; }
      .result-bullet::before { content: "•"; color: #74d6a4; }
      .summary-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin-bottom: 12px; }
      .summary-chip {
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(255,255,255,0.045);
        border: 1px solid rgba(255,255,255,0.08);
      }
      .summary-chip b { display: block; font-size: 12px; color: var(--muted); margin-bottom: 4px; font-weight: 600; }
      .summary-chip span { display: block; font-size: 15px; color: #fff6dd; font-weight: 700; }
      .candidate-list { display: grid; gap: 12px; }
      .candidate-card {
        padding: 14px;
        border-radius: 18px;
        background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.03));
        border: 1px solid rgba(255,255,255,0.10);
      }
      .candidate-top { display: flex; justify-content: space-between; gap: 10px; align-items: baseline; }
      .candidate-date { font-size: 18px; font-weight: 800; color: #fff8e5; }
      .candidate-score { font-size: 13px; color: #b9f3d8; }
      .candidate-meta { margin-top: 10px; display: grid; gap: 8px; }
      .candidate-tagline { color: var(--muted); font-size: 12px; line-height: 1.7; }
      .mini-list { display: grid; gap: 6px; margin-top: 8px; }
      .mini-item { font-size: 13px; line-height: 1.7; color: rgba(255,255,255,0.88); }
      .mini-item strong { color: #fff2bf; }
      .empty-state {
        padding: 18px;
        border-radius: 18px;
        background: rgba(255,255,255,0.04);
        border: 1px dashed rgba(255,255,255,0.14);
        color: var(--muted);
        line-height: 1.8;
      }
      .two-col-list { display: grid; gap: 10px; grid-template-columns: 1fr; }
      @media (min-width: 620px) { .two-col-list { grid-template-columns: 1fr 1fr; } }
      .note-box {
        padding: 12px 14px;
        border-radius: 16px;
        background: rgba(255,255,255,0.035);
        border: 1px solid rgba(255,255,255,0.08);
      }
      .note-box h4 {
        margin: 0 0 8px;
        font-size: 13px;
        color: #fff2bf;
        letter-spacing: 0.04em;
      }
      .boundary-grid { display: grid; gap: 10px; margin-top: 12px; grid-template-columns: 1fr; }
      @media (min-width: 720px) { .boundary-grid { grid-template-columns: 1fr 1fr; } }
      .fold-box {
        margin-top: 12px;
        border-radius: 18px;
        border: 1px solid rgba(255,255,255,0.08);
        background: rgba(255,255,255,0.03);
        overflow: hidden;
      }
      .fold-head {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        align-items: center;
        padding: 12px 14px;
        cursor: pointer;
        color: #fff2bf;
        font-size: 13px;
      }
      .fold-body {
        display: none;
        padding: 0 14px 14px;
      }
      .fold-box.open .fold-body { display: block; }
      .error { color: rgba(251,113,133,0.95); }
      .pill { display:inline-flex; align-items:center; gap:8px; padding:8px 12px; border-radius:999px; background: rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.12); font-size:12px; color: var(--muted); }
      .hero-pills { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 18px; }
      .quick-nav {
        display: flex;
        gap: 10px;
        flex-wrap: nowrap;
        margin: 16px 0 6px;
        position: sticky;
        top: 10px;
        z-index: 4;
        padding: 10px 12px;
        border-radius: 18px;
        background: rgba(7, 17, 31, 0.68);
        backdrop-filter: blur(14px);
        border: 1px solid rgba(255,255,255,0.08);
        overflow-x: auto;
        overflow-y: hidden;
        -webkit-overflow-scrolling: touch;
        scrollbar-width: none;
      }
      .quick-nav::-webkit-scrollbar { display: none; }
      .quick-link {
        flex: 0 0 auto;
        padding: 9px 14px;
        border-radius: 999px;
        background: rgba(255,255,255,0.05);
        border: 1px solid rgba(255,255,255,0.08);
        color: var(--text);
        font-size: 12px;
      }
      .quick-link:hover { border-color: rgba(116,214,164,0.30); color: #ecfff5; }
      .footer { margin-top: 20px; color: var(--muted); font-size: 12px; text-align: center; }
      .k { color: rgba(255,255,255,0.88); font-weight: 700; }
      .status-ok { color: #86efac; }
      .status-warn { color: #fbbf24; }
      .span-2 { grid-column: 1 / -1; }
      .section-chip {
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 6px 10px;
        border-radius: 999px;
        background: rgba(243,201,105,0.12);
        border: 1px solid rgba(243,201,105,0.18);
        color: #fff2bf;
        font-size: 12px;
      }
      .pillar-grid { display: grid; gap: 10px; grid-template-columns: repeat(2, minmax(0, 1fr)); margin: 12px 0; }
      @media (min-width: 620px) { .pillar-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
      .pillar-card {
        padding: 12px;
        border-radius: 16px;
        background: rgba(255,255,255,0.045);
        border: 1px solid rgba(255,255,255,0.08);
        text-align: center;
      }
      .pillar-card b { display: block; font-size: 12px; color: var(--muted); margin-bottom: 6px; font-weight: 600; }
      .pillar-card span { display: block; font-size: 24px; font-weight: 800; color: #fff8e5; letter-spacing: 0.06em; }
      .meter-list { display: grid; gap: 10px; margin-top: 10px; }
      .meter-row { display: grid; gap: 6px; }
      .meter-top { display: flex; justify-content: space-between; gap: 12px; font-size: 12px; color: var(--muted); }
      .meter-bar {
        height: 10px;
        border-radius: 999px;
        background: rgba(255,255,255,0.06);
        overflow: hidden;
      }
      .meter-fill {
        height: 100%;
        border-radius: inherit;
        background: linear-gradient(90deg, rgba(116,214,164,0.9), rgba(243,201,105,0.88));
      }
      .action-row {
        display: flex;
        justify-content: flex-end;
        gap: 10px;
        margin-top: 12px;
        flex-wrap: wrap;
      }
      .ghost-btn {
        appearance: none;
        border: 1px solid rgba(255,255,255,0.10);
        background: rgba(255,255,255,0.04);
        color: var(--muted);
        border-radius: 999px;
        padding: 8px 12px;
        font-size: 12px;
        cursor: pointer;
      }
      .ghost-btn:hover { color: #eefcf6; border-color: rgba(116,214,164,0.26); }
      .toast {
        position: fixed;
        right: 18px;
        bottom: 18px;
        z-index: 8;
        padding: 12px 14px;
        border-radius: 14px;
        background: rgba(7,17,31,0.88);
        border: 1px solid rgba(255,255,255,0.10);
        color: #eefcf6;
        box-shadow: var(--shadow);
        opacity: 0;
        transform: translateY(10px);
        pointer-events: none;
        transition: opacity 180ms ease, transform 180ms ease;
      }
      .toast.show {
        opacity: 1;
        transform: translateY(0);
      }
      @media (max-width: 820px) {
        .wrap {
          padding: 14px 12px 44px;
        }
        .topbar {
          flex-direction: column;
          align-items: stretch;
        }
        .brand {
          font-size: 24px;
        }
        .hero {
          margin-top: 14px;
          padding: 18px;
          border-radius: 22px;
        }
        .hero h1 {
          margin: 12px 0 10px;
          font-size: clamp(28px, 9vw, 42px);
        }
        .hero p {
          font-size: 14px;
          line-height: 1.75;
        }
        .hero-stats {
          grid-template-columns: 1fr;
        }
        .section-head {
          flex-direction: column;
          align-items: flex-start;
          margin: 20px 0 10px;
        }
        .section-head h2 {
          font-size: 20px;
        }
        .section-head p {
          max-width: none;
        }
        .card {
          padding: 14px;
          border-radius: 20px;
        }
        .card h2 {
          font-size: 17px;
        }
        .btns {
          gap: 8px;
        }
        button,
        .ghost-btn {
          width: 100%;
          justify-content: center;
          text-align: center;
        }
        .out {
          min-height: 96px;
          max-height: none;
          overflow: visible;
          font-size: 13px;
          line-height: 1.65;
        }
        .summary-grid {
          grid-template-columns: 1fr;
        }
        .candidate-top {
          flex-direction: column;
          align-items: flex-start;
        }
        .pillar-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .action-row {
          justify-content: stretch;
        }
        .toast {
          left: 12px;
          right: 12px;
          bottom: 12px;
        }
      }
      @media (max-width: 520px) {
        .wrap {
          padding: 10px 10px 32px;
        }
        .hero {
          padding: 16px 14px;
        }
        .eyebrow,
        .pill,
        .quick-link {
          font-size: 11px;
        }
        .sub,
        .card-lead,
        .hint,
        .candidate-tagline,
        .mini-item,
        .result-line,
        .result-bullet {
          font-size: 12px;
        }
        input, select, textarea {
          padding: 12px;
          font-size: 16px;
        }
        .summary-chip {
          padding: 10px 12px;
        }
        .summary-chip span {
          font-size: 14px;
        }
        .candidate-date {
          font-size: 16px;
        }
        .candidate-card,
        .note-box,
        .result-block,
        .pillar-card {
          border-radius: 14px;
        }
        .pillar-card span {
          font-size: 20px;
        }
      }
      @keyframes shimmer {
        from { transform: translateX(-100%); }
        to { transform: translateX(100%); }
      }
      @keyframes pulse {
        0%, 100% { transform: scale(0.85); opacity: 0.55; }
        50% { transform: scale(1.1); opacity: 1; }
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="topbar">
        <div>
          <div class="brand">gosuan</div>
          <div class="sub">把传统命理规则、择日逻辑和 AI 解读整理成一个更易读、更可复核的个人工具。</div>
        </div>
        <div class="pill">
          <span id="ai-status">AI 状态读取中</span>
          <a href="/docs" target="_blank" rel="noreferrer">Swagger</a>
        </div>
      </div>

      <section class="hero">
        <div class="hero-grid">
          <div>
            <div class="eyebrow">规则可复核 · 输出更像报告 · 手机端也顺手</div>
            <h1>一页里完成命盘、财运、择日、起卦和今日运势</h1>
            <p>这不是只会吐 JSON 的演示页，而是把“结构化规则计算”和“更像人在说话的解释”结合在一起。你填完基础信息后，可以连续跑多个模块，拿到更适合直接阅读的结果。</p>
            <div class="hero-pills">
              <div class="pill">八字命盘</div>
              <div class="pill">财运结构</div>
              <div class="pill">择日推荐</div>
              <div class="pill">梅花起卦</div>
              <div class="pill">今日运势</div>
            </div>
            <div class="hero-stats">
              <div class="stat">
                <b>5</b>
                <span>一个页面覆盖五类常用能力，减少来回切换。</span>
              </div>
              <div class="stat">
                <b>可追溯</b>
                <span>保留结构化数据基础，不会只给模糊结论。</span>
              </div>
            </div>
          </div>
          <div class="hero-panel">
            <h3>这一页适合怎么用</h3>
            <div class="feature-list">
              <div class="feature-item">
                <strong>先填个人信息</strong>
                <span>出生时间越精确，命盘、择日和起卦里的细节判断越稳定。</span>
              </div>
              <div class="feature-item">
                <strong>先看结构，再看 AI</strong>
                <span>建议先看规则结果，再决定是否用 AI 生成更长、更个性化的中文解读。</span>
              </div>
              <div class="feature-item">
                <strong>把它当辅助，不当裁决</strong>
                <span>适合做思路整理和备选方案，不建议把任何一条输出直接当成绝对结论。</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <nav class="quick-nav">
        <a class="quick-link" href="#card-person">基础资料</a>
        <a class="quick-link" href="#card-bazi">八字命盘</a>
        <a class="quick-link" href="#card-wealth">财运报告</a>
        <a class="quick-link" href="#card-select">择日推荐</a>
        <a class="quick-link" href="#card-divine">梅花起卦</a>
        <a class="quick-link" href="#card-daily">今日运势</a>
      </nav>

      <div class="section-head">
        <div>
          <div class="section-chip">基础档案</div>
          <h2>先把个人信息录完整</h2>
        </div>
        <p>后面的命盘、择日、起卦、每日运势都共用这一组资料。录一次，整页都能直接用。</p>
      </div>

      <div class="grid">
        <div class="card span-2" id="card-person">
          <h2>个人信息（用于命盘/择日/算卦）</h2>
          <div class="card-lead">把基础资料录完整后，下面所有模块都能直接复用，不需要重复填写。</div>
          <div class="row two">
            <div>
              <label>最近使用档案</label>
              <select id="profileHistory">
                <option value="">当前浏览器 / 当前 IP 暂无历史档案</option>
              </select>
            </div>
            <div>
              <label>档案操作</label>
              <div class="btns" style="margin-top: 0;">
                <button class="secondary" onclick="saveCurrentArchive(true)">保存当前档案</button>
                <button class="secondary" onclick="clearProfileArchives()">清空缓存</button>
              </div>
            </div>
          </div>
          <div class="row two">
            <div>
              <label>称呼</label>
              <input id="name" placeholder="例如：张三" value="张三" />
            </div>
            <div>
              <label>性别</label>
              <select id="gender">
                <option value="male" selected>男</option>
                <option value="female">女</option>
              </select>
            </div>
          </div>
          <div class="row two">
            <div>
              <label>出生时间</label>
              <input id="birth" placeholder="1995-08-17 14:30" value="1995-08-17 14:30" />
            </div>
            <div>
              <label>时区</label>
              <input id="tz" placeholder="Asia/Shanghai" value="Asia/Shanghai" />
            </div>
          </div>
          <div class="hint">
            - 出生时间建议写到<strong class="k">小时+分钟</strong>，否则择日/起卦的“细节差异”会变大。<br/>
            - 本工具输出为<strong class="k">可复核规则结果</strong> +（可选）AI 文案，不做投资/医疗/法律承诺。
          </div>
        </div>

        <div class="card" id="card-bazi">
          <h2>算命：八字命盘</h2>
          <div class="card-lead">更适合先看结构，再决定是否继续做财运或择日。</div>
          <div class="btns">
            <button onclick="runBazi()">生成命盘</button>
            <button class="secondary" onclick="clearOut('out-bazi')">清空</button>
          </div>
          <div class="out" id="out-bazi"></div>
        </div>

        <div class="card" id="card-wealth">
          <h2>算财运：结构化建议（可选 AI）</h2>
          <div class="card-lead">先给出可复核的结构建议，再决定要不要接 AI 写成更完整的中文报告。</div>
          <div class="row two">
            <div>
              <label>启用 AI 文案</label>
              <select id="wealth-ai">
                <option value="false" selected>否</option>
                <option value="true">是</option>
              </select>
            </div>
            <div>
              <label>模型名（可空）</label>
              <input id="wealth-model" placeholder="例如：doubao-1-5-pro-32k-250115" value="" />
            </div>
          </div>
          <div class="btns">
            <button onclick="runWealth()">生成财运报告</button>
            <button class="secondary" onclick="probeAi()">检查 AI 连接</button>
            <button class="secondary" onclick="clearOut('out-wealth')">清空</button>
          </div>
          <div class="out" id="out-wealth"></div>
          <div class="hint">
            若启用 AI：当前页面会自动读取服务端已配置的模型；如果连接失败，先点“检查 AI 连接”，再根据提示核对 key、模型名和服务权限。
          </div>
        </div>

        <div class="card" id="card-select">
          <h2>择日（手机端友好）：在时间段内找最合适</h2>
          <div class="card-lead">适合搬迁、动工、开业、婚嫁等场景，给你一组可解释的候选日，而不是只甩一个日期。</div>
          <div class="boundary-grid">
            <div class="note-box">
              <h4>当前这版依据了什么</h4>
              <div class="mini-item">命主出生时间、生肖与日期冲合关系</div>
              <div class="mini-item">黄历“宜 / 忌”关键词</div>
              <div class="mini-item">建除十二神、月破 / 岁破、你设置的时间范围与过滤条件</div>
            </div>
            <div class="note-box">
              <h4>当前还没有纳入什么</h4>
              <div class="mini-item">房屋朝向 / 坐向、入户门朝向、楼层</div>
              <div class="mini-item">多人同住时的宅主 / 居住者八字联动</div>
              <div class="mini-item">更细的入宅时辰、路线、分房或神位安置规则</div>
            </div>
          </div>
          <div class="hint">
            这意味着：当前“搬迁 / 入宅”结果更适合做<strong class="k">通用初筛</strong>，先帮你缩小日期范围；如果你后面要做到更传统、更完整的入宅择日，还需要把宅向、宅主、入住成员和入宅时辰一起纳入。
          </div>
          <div class="fold-box" id="move-advanced-box">
            <div class="fold-head" onclick="toggleFold('move-advanced-box')">
              <span>高级入宅信息（当前先记录并展示，后续可逐步接入评分）</span>
              <span>展开 / 收起</span>
            </div>
            <div class="fold-body">
              <div class="row two">
                <div>
                  <label>房屋坐向 / 朝向</label>
                  <input id="houseOrientation" placeholder="例如：坐北朝南" value="" />
                </div>
                <div>
                  <label>入户门朝向</label>
                  <input id="doorOrientation" placeholder="例如：东南" value="" />
                </div>
              </div>
              <div class="row two">
                <div>
                  <label>宅主姓名</label>
                  <input id="houseOwnerName" placeholder="例如：张三" value="" />
                </div>
                <div>
                  <label>宅主生辰</label>
                  <input id="houseOwnerBirth" placeholder="例如：1988-06-18 08:30" value="" />
                </div>
              </div>
              <div class="row two">
                <div>
                  <label>同住成员信息</label>
                  <input id="coResidentNotes" placeholder="例如：夫妻二人+孩子，孩子属兔" value="" />
                </div>
                <div>
                  <label>计划入宅时段</label>
                  <input id="moveTimeWindow" placeholder="例如：上午 / 9:00-11:00" value="" />
                </div>
              </div>
            </div>
          </div>
          <div class="row two">
            <div>
              <label>目的</label>
              <select id="purpose">
                <option value="move" selected>搬迁/入宅</option>
                <option value="construction">动工/装修</option>
                <option value="opening">开业</option>
                <option value="wedding">婚嫁</option>
              </select>
            </div>
            <div>
              <label>流派（默认最匹配）</label>
              <select id="school">
                <option value="best_fit" selected>best_fit（推荐）</option>
                <option value="strict">strict（严格）</option>
                <option value="almanac">almanac（仅宜忌）</option>
                <option value="jianchu">jianchu（仅建除）</option>
              </select>
            </div>
          </div>
          <div class="row two">
            <div>
              <label>开始日期</label>
              <input id="start" type="date" />
            </div>
            <div>
              <label>结束日期（包含）</label>
              <input id="end" type="date" />
            </div>
          </div>
          <div class="row two">
            <div>
              <label>返回数量</label>
              <input id="limit" type="number" min="1" max="50" value="10" />
            </div>
            <div>
              <label>最低分阈值</label>
              <input id="minScore" type="number" value="0" />
            </div>
          </div>
          <div class="row">
            <div>
              <label>排除日期（可选，逗号分隔：YYYY-MM-DD）</label>
              <input id="exclude" placeholder="例如：2026-04-05,2026-04-12" value="" />
            </div>
          </div>
          <div class="row two">
            <div>
              <label>必须命中“宜”</label>
              <select id="mustHitYi">
                <option value="false" selected>否</option>
                <option value="true">是</option>
              </select>
            </div>
            <div>
              <label>只取最合适 1 天</label>
              <select id="best">
                <option value="false" selected>否</option>
                <option value="true">是</option>
              </select>
            </div>
          </div>
          <div class="btns">
            <button onclick="runSelect()">开始择日</button>
            <button class="secondary" onclick="clearOut('out-select')">清空</button>
          </div>
          <div class="out" id="out-select"></div>
        </div>

        <div class="card" id="card-divine">
          <h2>算卦：梅花易数（个人起卦）</h2>
          <div class="card-lead">更适合在你真正准备问事的那一刻起卦，结果会更贴近当下问题。</div>
          <div class="row two">
            <div>
              <label>问事/起卦时间</label>
              <input id="qtime" type="datetime-local" />
            </div>
            <div>
              <label>个人种子（更贴合个人）</label>
              <select id="personalSeed">
                <option value="true" selected>是</option>
                <option value="false">否</option>
              </select>
            </div>
          </div>
          <div class="btns">
            <button onclick="runDivine()">起卦</button>
            <button class="secondary" onclick="clearOut('out-divine')">清空</button>
          </div>
          <div class="out" id="out-divine"></div>
          <div class="hint">
            建议在你<strong class="k">真正要问的那一刻</strong>起卦。若你希望更“针对个人”，保持“个人种子=是”。
          </div>
        </div>

        <div class="card" id="card-daily">
          <h2>个人今日运势：适宜/不宜/方向</h2>
          <div class="card-lead">把黄历宜忌、建除、冲煞和方位提示合并成更容易直接执行的日常建议。</div>
          <div class="row two">
            <div>
              <label>日期（不填则按时区取今天）</label>
              <input id="fday" type="date" />
            </div>
            <div>
              <label>说明</label>
              <input disabled value="包含：黄历宜忌 + 建除 + 冲煞 + 喜/财/福/太岁方位" />
            </div>
          </div>
          <div class="btns">
            <button onclick="runDailyFortune()">测算运势</button>
            <button class="secondary" onclick="clearOut('out-daily')">清空</button>
          </div>
          <div class="out" id="out-daily"></div>
          <div class="hint">
            “适合去哪里/不适合去哪里”以<strong class="k">方位</strong>表达（喜神/财神/福神/太岁）。如果你要“具体城市/场所”建议，需要再接入你的常住地与出行目的。
          </div>
        </div>
      </div>

      <div class="footer">
        <div>提示：手机端建议添加到桌面快捷方式，体验更像 App。</div>
      </div>
    </div>
    <div id="toast" class="toast"></div>

    <script>
      function nowDateISO() {
        const d = new Date();
        const pad = n => String(n).padStart(2,'0');
        return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
      }
      function addDaysISO(days) {
        const d = new Date();
        d.setDate(d.getDate() + days);
        const pad = n => String(n).padStart(2,'0');
        return `${d.getFullYear()}-${pad(d.getMonth()+1)}-${pad(d.getDate())}`;
      }
      function initDefaults() {
        const start = document.getElementById('start');
        const end = document.getElementById('end');
        if (!start.value) start.value = nowDateISO();
        if (!end.value) end.value = addDaysISO(60);
        const qtime = document.getElementById('qtime');
        if (!qtime.value) {
          const dt = new Date();
          dt.setMinutes(dt.getMinutes() - dt.getTimezoneOffset());
          qtime.value = dt.toISOString().slice(0,16);
        }
        const fday = document.getElementById('fday');
        if (!fday.value) fday.value = nowDateISO();
      }
      initDefaults();
      let storageScopeKey = "browser";
      const MAX_ARCHIVES = 8;
      function scopedStorageKey(baseKey) {
        return `${baseKey}:${storageScopeKey}`;
      }
      async function loadClientContext() {
        try {
          const resp = await fetch("/client-context");
          const data = await resp.json();
          if (data && data.client_ip) {
            storageScopeKey = `ip:${data.client_ip}`;
          }
        } catch (err) {}
      }

      function loadProfileCache() {
        try {
          const raw = window.localStorage.getItem(scopedStorageKey("gosuan.profile"));
          if (!raw) return;
          const data = JSON.parse(raw);
          if (data.name) document.getElementById("name").value = data.name;
          if (data.gender) document.getElementById("gender").value = data.gender;
          if (data.birth_dt) document.getElementById("birth").value = data.birth_dt;
          if (data.tz) document.getElementById("tz").value = data.tz;
        } catch (err) {}
      }
      function saveProfileCache() {
        try {
          const data = collectProfileCacheData();
          window.localStorage.setItem(scopedStorageKey("gosuan.profile"), JSON.stringify(data));
        } catch (err) {}
      }
      ["name", "gender", "birth", "tz"].forEach(function(id) {
        var el = document.getElementById(id);
        if (!el) return;
        el.addEventListener("change", saveProfileCache);
        el.addEventListener("blur", saveProfileCache);
      });
      function loadMoveCache() {
        try {
          const raw = window.localStorage.getItem(scopedStorageKey("gosuan.moveProfile"));
          if (!raw) return;
          const data = JSON.parse(raw);
          if (data.house_orientation) document.getElementById("houseOrientation").value = data.house_orientation;
          if (data.door_orientation) document.getElementById("doorOrientation").value = data.door_orientation;
          if (data.house_owner_name) document.getElementById("houseOwnerName").value = data.house_owner_name;
          if (data.house_owner_birth) document.getElementById("houseOwnerBirth").value = data.house_owner_birth;
          if (data.co_resident_notes) document.getElementById("coResidentNotes").value = data.co_resident_notes;
          if (data.move_time_window) document.getElementById("moveTimeWindow").value = data.move_time_window;
        } catch (err) {}
      }
      function saveMoveCache() {
        try {
          const data = collectMoveCacheData();
          window.localStorage.setItem(scopedStorageKey("gosuan.moveProfile"), JSON.stringify(data));
        } catch (err) {}
      }
      function collectProfileCacheData() {
        return {
          name: document.getElementById("name").value,
          gender: document.getElementById("gender").value,
          birth_dt: document.getElementById("birth").value,
          tz: document.getElementById("tz").value,
        };
      }
      function collectMoveCacheData() {
        return {
          house_orientation: document.getElementById("houseOrientation").value,
          door_orientation: document.getElementById("doorOrientation").value,
          house_owner_name: document.getElementById("houseOwnerName").value,
          house_owner_birth: document.getElementById("houseOwnerBirth").value,
          co_resident_notes: document.getElementById("coResidentNotes").value,
          move_time_window: document.getElementById("moveTimeWindow").value,
        };
      }
      function getArchiveHistory() {
        try {
          const raw = window.localStorage.getItem(scopedStorageKey("gosuan.profileHistory"));
          const data = raw ? JSON.parse(raw) : [];
          return Array.isArray(data) ? data : [];
        } catch (err) {
          return [];
        }
      }
      function archiveLabel(item) {
        const base = item && item.profile ? item.profile : {};
        const name = base.name || "未命名";
        const birth = base.birth_dt || "未填生日";
        return `${name}｜${birth}`;
      }
      function renderProfileHistory() {
        const select = document.getElementById("profileHistory");
        if (!select) return;
        const archives = getArchiveHistory();
        const options = ['<option value="">选择历史档案并自动带出</option>'];
        archives.forEach((item, idx) => {
          options.push(`<option value="${idx}">${escapeHtml(archiveLabel(item))}</option>`);
        });
        select.innerHTML = options.join("");
      }
      function applyArchiveItem(item) {
        if (!item) return;
        const profile = item.profile || {};
        const move = item.move || {};
        if (profile.name != null) document.getElementById("name").value = profile.name;
        if (profile.gender) document.getElementById("gender").value = profile.gender;
        if (profile.birth_dt != null) document.getElementById("birth").value = profile.birth_dt;
        if (profile.tz != null) document.getElementById("tz").value = profile.tz;
        if (move.house_orientation != null) document.getElementById("houseOrientation").value = move.house_orientation;
        if (move.door_orientation != null) document.getElementById("doorOrientation").value = move.door_orientation;
        if (move.house_owner_name != null) document.getElementById("houseOwnerName").value = move.house_owner_name;
        if (move.house_owner_birth != null) document.getElementById("houseOwnerBirth").value = move.house_owner_birth;
        if (move.co_resident_notes != null) document.getElementById("coResidentNotes").value = move.co_resident_notes;
        if (move.move_time_window != null) document.getElementById("moveTimeWindow").value = move.move_time_window;
        saveProfileCache();
        saveMoveCache();
      }
      function saveCurrentArchive(showFeedback) {
        try {
          const profile = collectProfileCacheData();
          const move = collectMoveCacheData();
          if (!profile.name && !profile.birth_dt) return;
          const archive = {
            key: `${profile.name || ""}|${profile.gender || ""}|${profile.birth_dt || ""}|${storageScopeKey}`,
            profile,
            move,
            updated_at: new Date().toISOString(),
          };
          const archives = getArchiveHistory().filter(item => item && item.key !== archive.key);
          archives.unshift(archive);
          window.localStorage.setItem(
            scopedStorageKey("gosuan.profileHistory"),
            JSON.stringify(archives.slice(0, MAX_ARCHIVES))
          );
          renderProfileHistory();
          if (showFeedback) showToast("当前档案已保存");
        } catch (err) {
          if (showFeedback) showToast("保存档案失败");
        }
      }
      function clearProfileArchives() {
        try {
          window.localStorage.removeItem(scopedStorageKey("gosuan.profile"));
          window.localStorage.removeItem(scopedStorageKey("gosuan.moveProfile"));
          window.localStorage.removeItem(scopedStorageKey("gosuan.profileHistory"));
          document.getElementById("profileHistory").innerHTML = '<option value="">当前浏览器 / 当前 IP 暂无历史档案</option>';
          showToast("当前 IP 下的缓存已清空");
        } catch (err) {
          showToast("清空缓存失败");
        }
      }
      ["houseOrientation", "doorOrientation", "houseOwnerName", "houseOwnerBirth", "coResidentNotes", "moveTimeWindow"].forEach(function(id) {
        var el = document.getElementById(id);
        if (!el) return;
        el.addEventListener("change", saveMoveCache);
        el.addEventListener("blur", saveMoveCache);
      });
      document.getElementById("profileHistory").addEventListener("change", function(e) {
        const value = e && e.target ? e.target.value : "";
        if (value === "") return;
        const archives = getArchiveHistory();
        const item = archives[Number(value)];
        if (!item) return;
        applyArchiveItem(item);
        showToast("历史档案已带出");
      });
      loadClientContext().finally(function() {
        loadProfileCache();
        loadMoveCache();
        renderProfileHistory();
      });

      async function loadAiStatus() {
        try {
          const resp = await fetch("/ai-status");
          const data = await resp.json();
          const el = document.getElementById("ai-status");
          const modelInput = document.getElementById("wealth-model");
          if (modelInput && !modelInput.value) modelInput.value = data.model || "";
          if (data.configured) {
            el.textContent = `AI 已配置：${data.provider_label} / ${data.model}`;
            el.classList.add("status-ok");
          } else {
            el.textContent = "AI 未配置";
            el.classList.add("status-warn");
          }
        } catch (err) {
          const el = document.getElementById("ai-status");
          el.textContent = "AI 状态不可用";
          el.classList.add("status-warn");
        }
      }
      loadAiStatus();

      function getPerson() {
        return {
          name: document.getElementById('name').value.trim() || "匿名",
          gender: document.getElementById('gender').value,
          birth_dt: document.getElementById('birth').value.trim(),
          tz: document.getElementById('tz').value.trim() || "Asia/Shanghai",
          location: null,
        };
      }
      function toggleFold(id) {
        var el = document.getElementById(id);
        if (!el) return;
        el.classList.toggle("open");
      }
      function clearOut(id) {
        const el = document.getElementById(id);
        el.textContent = "";
        el.innerHTML = "";
        el.classList.remove("error");
        el.classList.remove("is-loading");
      }
      function setOut(id, obj) {
        const el = document.getElementById(id);
        el.classList.remove("error");
        el.textContent = typeof obj === 'string' ? obj : JSON.stringify(obj, null, 2);
      }
      function setErr(id, err) {
        const el = document.getElementById(id);
        el.classList.remove("is-loading");
        el.classList.add("error");
        el.textContent = (err && err.message) ? err.message : String(err);
      }
      function showToast(message) {
        const toast = document.getElementById("toast");
        if (!toast) return;
        toast.textContent = message;
        toast.classList.add("show");
        clearTimeout(window.__gosuanToastTimer);
        window.__gosuanToastTimer = setTimeout(() => toast.classList.remove("show"), 1800);
      }
      function setLoading(id, text) {
        const el = document.getElementById(id);
        el.classList.remove("error");
        el.classList.add("is-loading");
        el.innerHTML = `
          <div class="loading-box">
            <div>${escapeHtml(text || "正在生成结果，请稍候…")}</div>
            <div class="loading-dotline">
              <span class="loading-dot"></span>
              <span class="loading-dot"></span>
              <span class="loading-dot"></span>
            </div>
          </div>
        `;
      }
      function appendActionRow(id, summaryText) {
        if (!summaryText) return;
        const el = document.getElementById(id);
        if (!el) return;
        const row = document.createElement("div");
        row.className = "action-row";
        const btn = document.createElement("button");
        btn.className = "ghost-btn";
        btn.textContent = "复制摘要";
        btn.onclick = async () => {
          try {
            await navigator.clipboard.writeText(summaryText);
            showToast("摘要已复制");
          } catch (err) {
            showToast("复制失败，请手动选择文本");
          }
        };
        row.appendChild(btn);
        el.appendChild(row);
      }
      function escapeHtml(text) {
        return String(text)
          .split("&").join("&amp;")
          .split("<").join("&lt;")
          .split(">").join("&gt;")
          .split('"').join("&quot;")
          .split("'").join("&#39;");
      }
      function setRichOut(id, title, body) {
        const el = document.getElementById(id);
        el.classList.remove("error");
        const lines = String(body || "").split("\\n");
        const chunks = [];
        if (title) chunks.push(`<div class="result-title">${escapeHtml(title)}</div>`);
        let inBlock = false;
        lines.forEach(line => {
          const trimmed = line.trim();
          if (!trimmed) {
            if (inBlock) {
              chunks.push(`</div>`);
              inBlock = false;
            }
            return;
          }
          if (!inBlock) {
            chunks.push(`<div class="result-block">`);
            inBlock = true;
          }
          if (trimmed.startsWith("- ")) {
            chunks.push(`<div class="result-bullet">${escapeHtml(trimmed.slice(2))}</div>`);
          } else {
            chunks.push(`<div class="result-line">${escapeHtml(trimmed)}</div>`);
          }
        });
        if (inBlock) chunks.push(`</div>`);
        el.innerHTML = chunks.join("");
      }
      function renderSimpleCard(id, title, body) {
        setRichOut(id, title, body);
        const el = document.getElementById(id);
        el.classList.remove("is-loading");
        appendActionRow(id, `${title || ""}\\n${body || ""}`.trim());
      }
      function renderBaziResult(payload) {
        const wrap = document.getElementById("out-bazi");
        wrap.classList.remove("is-loading");
        wrap.classList.remove("error");
        const data = payload.data || {};
        const wuxing = Object.entries(data.wuxing_counts || {}).sort((a, b) => b[1] - a[1]);
        const maxValue = wuxing.length ? Math.max(...wuxing.map(([, v]) => Number(v) || 0), 1) : 1;
        const pillars = [
          ["年柱", data.year ? `${data.year.stem}${data.year.branch}` : "-"],
          ["月柱", data.month ? `${data.month.stem}${data.month.branch}` : "-"],
          ["日柱", data.day ? `${data.day.stem}${data.day.branch}` : "-"],
          ["时柱", data.hour ? `${data.hour.stem}${data.hour.branch}` : "-"],
        ];
        wrap.innerHTML = [
          `<div class="result-title">${escapeHtml(payload.title || "八字命盘")}</div>`,
          `<div class="summary-grid">`,
          `<div class="summary-chip"><b>日主</b><span>${escapeHtml(data.day_master || "-")}</span></div>`,
          `<div class="summary-chip"><b>生肖</b><span>${escapeHtml((data.raw && data.raw.lunar && data.raw.lunar.animal) || "-")}</span></div>`,
          `</div>`,
          `<div class="pillar-grid">${pillars.map(([label, value]) => `<div class="pillar-card"><b>${escapeHtml(label)}</b><span>${escapeHtml(value)}</span></div>`).join("")}</div>`,
          `<div class="note-box"><h4>五行分布</h4><div class="meter-list">${wuxing.map(([name, value]) => `
            <div class="meter-row">
              <div class="meter-top"><span>${escapeHtml(name)}</span><span>${escapeHtml(value)}</span></div>
              <div class="meter-bar"><div class="meter-fill" style="width:${Math.max(8, Math.round((Number(value) || 0) / maxValue * 100))}%"></div></div>
            </div>
          `).join("")}</div></div>`,
          `<div class="result-block"><div class="result-line">${escapeHtml(payload.summary || "命盘结果已生成。")}</div></div>`,
        ].join("");
        appendActionRow("out-bazi", `${payload.title || ""}\\n${payload.summary || ""}`.trim());
      }
      function renderWealthResult(payload) {
        const wrap = document.getElementById("out-wealth");
        wrap.classList.remove("is-loading");
        wrap.classList.remove("error");
        const data = payload.data || {};
        const dailyCtx = data.structure && data.structure.daily_wealth_context ? data.structure.daily_wealth_context : {};
        const suggestions = data.suggestions || [];
        const cautions = data.cautions || [];
        const html = [
          `<div class="result-title">${escapeHtml(payload.title || "财运结构简报")}</div>`,
          `<div class="summary-grid">`,
          `<div class="summary-chip"><b>概览</b><span>${escapeHtml((data.overview || "未生成概览").slice(0, 36) || "未生成概览")}</span></div>`,
          `<div class="summary-chip"><b>AI 解读</b><span>${data.ai_text ? "已生成" : "未启用 / 未生成"}</span></div>`,
          `<div class="summary-chip"><b>当天财位</b><span>${escapeHtml(dailyCtx.wealth_direction || "暂无")}</span></div>`,
          `<div class="summary-chip"><b>股票偏好数字</b><span>${escapeHtml(listText(dailyCtx.stock_preferred_digits, "暂无"))}</span></div>`,
          `</div>`,
          `<div class="two-col-list">`,
          `<div class="note-box"><h4>适合优先做的事</h4>${suggestions.length ? suggestions.map(x => `<div class="mini-item">${escapeHtml(x)}</div>`).join("") : `<div class="mini-item">暂无明显建议。</div>`}</div>`,
          `<div class="note-box"><h4>需要特别留意</h4>${cautions.length ? cautions.map(x => `<div class="mini-item">${escapeHtml(x)}</div>`).join("") : `<div class="mini-item">当前没有特别突出的风险提示。</div>`}</div>`,
          `</div>`,
          `<div class="two-col-list">`,
          `<div class="note-box"><h4>当天财位与处理</h4><div class="mini-item"><strong>财位：</strong>${escapeHtml(dailyCtx.wealth_direction || "暂无")}</div><div class="mini-item"><strong>辅助方位：</strong>${escapeHtml(listText(dailyCtx.support_directions, "暂无"))}</div><div class="mini-item"><strong>回避方位：</strong>${escapeHtml(listText(dailyCtx.avoid_directions, "暂无"))}</div><div class="mini-item">若人在非财位，先做复盘、沟通、信息收集和小额安排，少做重决策。</div></div>`,
          `<div class="note-box"><h4>股票 / 彩票偏向</h4><div class="mini-item"><strong>股票偏好数字：</strong>${escapeHtml(listText(dailyCtx.stock_preferred_digits, "暂无"))}</div><div class="mini-item"><strong>股票避忌数字：</strong>${escapeHtml(listText(dailyCtx.stock_avoid_digits, "暂无"))}</div><div class="mini-item"><strong>股票优先关键词：</strong>${escapeHtml(listText(dailyCtx.stock_theme_keywords, "暂无"))}</div><div class="mini-item"><strong>股票回避关键词：</strong>${escapeHtml(listText(dailyCtx.stock_avoid_keywords, "暂无"))}</div><div class="mini-item"><strong>彩票通用号：</strong>${escapeHtml(listText(dailyCtx.lottery_numbers, "暂无"))}</div></div>`,
          `</div>`,
        ];
        if (data.ai_text) {
          html.push(`<div class="result-block"><div class="result-line">${escapeHtml("AI 补充解读")}</div>${escapeHtml(data.ai_text).split("\\n").join("<br/>")}</div>`);
        } else if (payload.summary) {
          html.push(`<div class="result-block">${escapeHtml(payload.summary).split("\\n").join("<br/>")}</div>`);
        }
        wrap.innerHTML = html.join("");
        appendActionRow("out-wealth", `${payload.title || ""}\\n${payload.summary || ""}`.trim());
      }
      function renderDailyResult(payload) {
        const wrap = document.getElementById("out-daily");
        wrap.classList.remove("is-loading");
        wrap.classList.remove("error");
        const data = payload.data || {};
        const good = data.good || [];
        const bad = data.bad || [];
        const notes = data.notes || [];
        const stockThemes = data.stock_theme_keywords || [];
        const stockAvoidThemes = data.stock_avoid_keywords || [];
        const stockCodeHints = data.stock_code_hints || [];
        const lotteryRecs = data.lottery_recommendations || {};
        const lotteryItems = Object.entries(lotteryRecs).map(([label, nums]) =>
          `<div class="mini-item"><strong>${escapeHtml(label)}：</strong>${escapeHtml(listText(nums, "暂无"))}</div>`
        ).join("");
        wrap.innerHTML = [
          `<div class="result-title">${escapeHtml(payload.title || "个人运势")}</div>`,
          `<div class="summary-grid">`,
          `<div class="summary-chip"><b>日期</b><span>${escapeHtml(data.day || "-")}</span></div>`,
          `<div class="summary-chip"><b>日况</b><span>${escapeHtml(`${data.day_ganzhi || "-"} · ${data.jianchu_12 || "-"}`)}</span></div>`,
          `<div class="summary-chip"><b>幸运数字</b><span>${escapeHtml(listText(data.lucky_numbers, "暂无"))}</span></div>`,
          `<div class="summary-chip"><b>幸运方位</b><span>${escapeHtml(data.lucky_direction || listText(data.go_directions, "按实际安排"))}</span></div>`,
          `<div class="summary-chip"><b>市场观察</b><span>${escapeHtml(data.stock_market_level || "暂无")}</span></div>`,
          `<div class="summary-chip"><b>生肖</b><span>${escapeHtml(data.zodiac || "-")}</span></div>`,
          `</div>`,
          `<div class="two-col-list">`,
          `<div class="note-box"><h4>今天更适合</h4>${good.length ? good.map(x => `<div class="mini-item">${escapeHtml(x)}</div>`).join("") : `<div class="mini-item">暂无特别突出的加分事项。</div>`}</div>`,
          `<div class="note-box"><h4>今天尽量避开</h4>${bad.length ? bad.map(x => `<div class="mini-item">${escapeHtml(x)}</div>`).join("") : `<div class="mini-item">暂无特别明确的避坑项。</div>`}</div>`,
          `</div>`,
          `<div class="two-col-list">`,
          `<div class="note-box"><h4>彩票娱乐号</h4><div class="mini-item"><strong>通用号：</strong>${escapeHtml(listText(data.lottery_numbers, "暂无"))}</div>${lotteryItems || `<div class="mini-item">暂无分彩种模板。</div>`}<div class="mini-item">仅供娱乐，不代表真实中奖概率。</div></div>`,
          `<div class="note-box"><h4>市场观察（非投资建议）</h4><div class="mini-item"><strong>等级：</strong>${escapeHtml(data.stock_market_level || "暂无")}</div><div class="mini-item"><strong>偏好数字：</strong>${escapeHtml(listText(data.stock_preferred_digits, "暂无"))}</div><div class="mini-item"><strong>避忌数字：</strong>${escapeHtml(listText(data.stock_avoid_digits, "暂无"))}</div><div class="mini-item"><strong>优先观察主题：</strong>${escapeHtml(listText(stockThemes, "暂无"))}</div><div class="mini-item"><strong>尽量回避主题：</strong>${escapeHtml(listText(stockAvoidThemes, "暂无"))}</div>${stockCodeHints.map(x => `<div class="mini-item">${escapeHtml(x)}</div>`).join("")}<div class="mini-item">${escapeHtml(data.stock_market_note || "暂无")}</div></div>`,
          `</div>`,
          `<div class="result-block"><div class="result-line">依据说明</div><div class="result-bullet">幸运方位：优先取当天喜神 / 财神 / 福神方位，属于黄历规则解释。</div><div class="result-bullet">幸运数字：按姓名、出生时间、当天日期生成稳定娱乐号，不是传统黄历原生字段。</div><div class="result-bullet">彩票娱乐号：按姓名、出生时间、当天日期生成确定性娱乐号，仅供娱乐。</div><div class="result-bullet">市场观察：结合生肖冲合、建除十二神与黄历交易相关宜忌生成；数字、主题词和代码形态提示也只是娱乐化观察，不是具体荐股。</div></div>`,
          notes.length ? `<div class="result-block"><div class="result-line">补充提醒</div>${notes.map(x => `<div class="result-bullet">${escapeHtml(x)}</div>`).join("")}</div>` : "",
        ].join("");
        appendActionRow("out-daily", `${payload.title || ""}\\n${payload.summary || ""}`.trim());
      }
      function renderSelectResult(data, name) {
        const wrap = document.getElementById("out-select");
        wrap.classList.remove("is-loading");
        wrap.classList.remove("error");
        const items = data["候选日"] || [];
        const extras = data["补充条件"] || [];
        if (!items.length) {
          wrap.innerHTML = `<div class="result-title">${escapeHtml(`${name}的择日建议`)}</div><div class="empty-state">这段时间里没有筛出合适日期，建议放宽条件、降低筛选门槛，或者换一个时间段再试。</div>`;
          if (extras.length) {
            wrap.innerHTML += `<div class="result-block"><div class="result-line">已记录的补充条件</div>${extras.map(x => `<div class="result-bullet">${escapeHtml(x)}</div>`).join("")}</div>`;
          }
          return;
        }
        const cards = items.slice(0, 3).map((item, idx) => `
          <div class="candidate-card">
            <div class="candidate-top">
              <div class="candidate-date">TOP ${idx + 1} · ${escapeHtml(item["日期"])} ${escapeHtml(item["星期"] || "")}</div>
              <div class="candidate-score">评分 ${escapeHtml(item["评分"] != null ? item["评分"] : "-")}</div>
            </div>
            <div class="candidate-meta">
              <div class="candidate-tagline">这一天在当前规则里更值得优先考虑，适合先拿去和实际安排做交叉确认。</div>
              <div class="mini-list">
                <div class="mini-item"><strong>理由：</strong>${escapeHtml(listText(item["理由"], "暂无明显加分点"))}</div>
                <div class="mini-item"><strong>提醒：</strong>${escapeHtml(listText(item["提醒"], "暂无明显风险提示"))}</div>
              </div>
            </div>
          </div>
        `).join("");
        wrap.innerHTML = [
          `<div class="result-title">${escapeHtml(`${name}的择日建议`)}</div>`,
          `<div class="summary-grid">`,
          `<div class="summary-chip"><b>目的</b><span>${escapeHtml(data["目的"] || "-")}</span></div>`,
          `<div class="summary-chip"><b>范围</b><span>${escapeHtml(`${data["开始日期"] || "-"} 至 ${data["结束日期"] || "-"}`)}</span></div>`,
          `</div>`,
          extras.length ? `<div class="result-block"><div class="result-line">已记录的补充条件</div>${extras.map(x => `<div class="result-bullet">${escapeHtml(x)}</div>`).join("")}</div>` : "",
          `<div class="candidate-list">${cards}</div>`,
          `<div class="result-block"><div class="result-line">说明：当前“搬迁 / 入宅”结果属于通用初筛，主要依据命主生日、黄历宜忌、建除与冲破规则，还没有把房屋朝向、宅主多人八字和入宅时辰纳入计算。</div></div>`,
          items.length > 3 ? `<div class="result-block"><div class="result-line">已为你展示评分最高的 3 天，其余候选日仍保留在本次结果里。</div></div>` : "",
        ].join("");
        const summaryLines = [
          `${name}的择日建议`,
          `目的：${data["目的"] || "-"}`,
          `范围：${data["开始日期"] || "-"} 至 ${data["结束日期"] || "-"}`,
        ];
        items.slice(0, 3).forEach((item, idx) => {
          summaryLines.push(`TOP ${idx + 1} ${item["日期"]} ${item["星期"] || ""} 评分 ${item["评分"]}`);
        });
        const summary = summaryLines.join("\\n");
        appendActionRow("out-select", summary);
      }
      function listText(items, emptyText) {
        return Array.isArray(items) && items.length ? items.join("、") : emptyText;
      }
      function formatBazi(data, name) {
        const wuxing = data.wuxing_counts
          ? Object.entries(data.wuxing_counts).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k}${v}`).join("，")
          : "暂无";
        const shishen = data.shishen
          ? Object.entries(data.shishen).map(([k, v]) => `${k}:${v}`).join("，")
          : "暂无";
        const lunar = data.raw && data.raw.lunar ? data.raw.lunar : {};
        return [
          `${name}的八字命盘`,
          `四柱：年柱 ${data.year.stem}${data.year.branch} | 月柱 ${data.month.stem}${data.month.branch} | 日柱 ${data.day.stem}${data.day.branch} | 时柱 ${data.hour.stem}${data.hour.branch}`,
          `日主：${data.day_master}`,
          `生肖：${lunar.animal || "未知"}`,
          `五行分布：${wuxing}`,
          `十神结构：${shishen}`,
          "提示：这里展示的是可复核的结构化排盘结果。"
        ].join("\\n");
      }
      function formatWealth(data, name) {
        const lines = [`${name}的财运结构简报`, data.overview, "", "适合优先做的事："];
        (data.suggestions || []).forEach(x => lines.push(`- ${x}`));
        if (!data.suggestions || !data.suggestions.length) lines.push("- 暂无明显建议。");
        lines.push("", "需要特别留意：");
        (data.cautions || []).forEach(x => lines.push(`- ${x}`));
        if (!data.cautions || !data.cautions.length) lines.push("- 当前没有特别突出的风险提示。");
        if (data.ai_text) lines.push("", "AI 补充解读：", data.ai_text);
        return lines.join("\\n");
      }
      function formatSelect(data, name) {
        const lines = [
          `${name}的择日建议`,
          `目的：${data["目的"] || "未说明"}`,
          `流派：${data["流派"] || "未说明"}`,
          `范围：${data["开始日期"]} 至 ${data["结束日期"]}`,
          ""
        ];
        const items = data["候选日"] || [];
        if (!items.length) {
          lines.push("这段时间里没有筛出合适日期，建议放宽条件或换一个时间段再试。");
          return lines.join("\\n");
        }
        items.forEach((item, idx) => {
          lines.push(`${idx + 1}. ${item["日期"]} ${item["星期"]} | 评分 ${item["评分"]}`);
          lines.push(`   理由：${listText(item["理由"], "暂无明显加分点")}`);
          lines.push(`   提醒：${listText(item["提醒"], "暂无明显风险提示")}`);
        });
        lines.push("", "说明：评分越高，代表在当前规则下越适合作为优先候选。");
        return lines.join("\\n");
      }
      function formatDivine(data, name) {
        return [
          `${name}的起卦结果`,
          `上卦：${data.upper.name}${data.upper.symbol}（${data.upper.element}）`,
          `下卦：${data.lower.name}${data.lower.symbol}（${data.lower.element}）`,
          `动爻：第 ${data.moving_line} 爻`,
          `起卦方式：${data.method}`,
          "提示：这个结果更适合作为后续断卦的基础。"
        ].join("\\n");
      }
      function formatDaily(data, name) {
        const lines = [
          `${name}在 ${data.day} 的个人运势`,
          `生肖：${data.zodiac} | 日干支：${data.day_ganzhi} | 建除：${data.jianchu_12}`,
          `幸运数字：${listText(data.lucky_numbers, "暂无")}`,
          `幸运方位：${data.lucky_direction || listText(data.go_directions, "按实际安排")}`,
          `市场观察等级：${data.stock_market_level || "暂无"}`,
          `偏好数字：${listText(data.stock_preferred_digits, "暂无")}`,
          `避忌数字：${listText(data.stock_avoid_digits, "暂无")}`,
          `黄历宜：${listText(data.yi, "无明显宜项")}`,
          `黄历忌：${listText(data.ji, "无明显忌项")}`,
          "",
          "今天更适合："
        ];
        (data.good || []).forEach(x => lines.push(`- ${x}`));
        if (!data.good || !data.good.length) lines.push("- 暂无特别突出的加分事项。");
        lines.push("", "今天尽量避开：");
        (data.bad || []).forEach(x => lines.push(`- ${x}`));
        if (!data.bad || !data.bad.length) lines.push("- 暂无特别明确的避坑项。");
        lines.push("", `适合去的方位：${listText(data.go_directions, "可按实际行程安排")}`);
        lines.push(`尽量回避的方位：${listText(data.avoid_directions, "暂无特别提示")}`);
        lines.push(`彩票娱乐号：${listText(data.lottery_numbers, "暂无")}`);
        if (data.lottery_recommendations) {
          Object.entries(data.lottery_recommendations).forEach(([label, nums]) => {
            lines.push(`${label}：${listText(nums, "暂无")}`);
          });
        }
        if (data.stock_theme_keywords) lines.push(`优先观察主题：${listText(data.stock_theme_keywords, "暂无")}`);
        if (data.stock_avoid_keywords) lines.push(`尽量回避主题：${listText(data.stock_avoid_keywords, "暂无")}`);
        if (data.stock_code_hints) data.stock_code_hints.forEach(x => lines.push(`- ${x}`));
        if (data.stock_market_note) lines.push(`市场观察：${data.stock_market_note}`);
        if (data.notes && data.notes.length) {
          lines.push("", "补充提醒：");
          data.notes.forEach(x => lines.push(`- ${x}`));
        }
        return lines.join("\\n");
      }
      async function postJSON(url, body) {
        const resp = await fetch(url, {
          method: "POST",
          headers: {"Content-Type":"application/json"},
          body: JSON.stringify(body),
        });
        const text = await resp.text();
        let data;
        try { data = JSON.parse(text); } catch (err) { data = text; }
        if (!resp.ok) {
          const detail = data && data.detail ? data.detail : text;
          throw new Error(`${resp.status} ${resp.statusText}\\n${detail}`);
        }
        return data;
      }

      async function runBazi() {
        try {
          const person = getPerson();
          saveCurrentArchive(false);
          setLoading("out-bazi", "正在生成八字命盘…");
          const data = await postJSON("/bazi?pretty_cn=true", person);
          renderBaziResult(data);
        } catch(e) { setErr("out-bazi", e); }
      }

      async function runWealth() {
        try {
          const person = getPerson();
          saveCurrentArchive(false);
          setLoading("out-wealth", "正在整理财运结构与建议…");
          const ai = document.getElementById("wealth-ai").value;
          const model = document.getElementById("wealth-model").value.trim();
          const qs = new URLSearchParams();
          qs.set("ai", ai);
          qs.set("pretty_cn", "true");
          if (model) qs.set("model", model);
          const data = await postJSON(`/wealth?${qs.toString()}`, person);
          renderWealthResult(data);
        } catch(e) { setErr("out-wealth", e); }
      }

      async function probeAi() {
        try {
          const person = getPerson();
          setLoading("out-wealth", "正在检查 AI 连接…");
          const model = document.getElementById("wealth-model").value.trim();
          const qs = new URLSearchParams();
          if (model) qs.set("model", model);
          const resp = await fetch(`/ai-probe?${qs.toString()}`, {
            method: "POST",
            headers: {"Content-Type":"application/json"},
            body: JSON.stringify(person),
          });
          const data = await resp.json();
          if (!resp.ok) throw new Error(data.detail || "AI 连接检测失败");
          renderSimpleCard("out-wealth", "AI 连接检测", data.message);
        } catch(e) { setErr("out-wealth", e); }
      }

      async function runSelect() {
        try {
          const person = getPerson();
          saveCurrentArchive(false);
          setLoading("out-select", "正在筛选候选吉日…");
          const purpose = document.getElementById("purpose").value;
          const school = document.getElementById("school").value;
          const start = document.getElementById("start").value;
          const end = document.getElementById("end").value;
          const limit = Number(document.getElementById("limit").value || 10);
          const best = document.getElementById("best").value === "true";
          const minScore = Number(document.getElementById("minScore").value || 0);
          const mustHitYi = document.getElementById("mustHitYi").value === "true";
          const excludeRaw = document.getElementById("exclude").value.trim();
          const exclude_dates = excludeRaw
            ? excludeRaw.split(",").map(s => s.trim()).filter(Boolean)
            : [];
          const body = {
            person,
            purpose,
            school,
            house_orientation: document.getElementById("houseOrientation").value.trim() || null,
            door_orientation: document.getElementById("doorOrientation").value.trim() || null,
            house_owner_name: document.getElementById("houseOwnerName").value.trim() || null,
            house_owner_birth: document.getElementById("houseOwnerBirth").value.trim() || null,
            co_resident_notes: document.getElementById("coResidentNotes").value.trim() || null,
            move_time_window: document.getElementById("moveTimeWindow").value.trim() || null,
            start,
            end,
            limit: best ? 1 : limit,
            prefer_weekend: false,
            avoid_weekend: false,
            exclude_dates,
            must_hit_yi: mustHitYi,
            min_score: minScore,
            days: 60
          };
          const data = await postJSON("/select-date?pretty_cn=true", body);
          renderSelectResult(data, person.name);
        } catch(e) { setErr("out-select", e); }
      }

      async function runDivine() {
        try {
          const person = getPerson();
          saveCurrentArchive(false);
          setLoading("out-divine", "正在起卦，请稍候…");
          const qtime = document.getElementById("qtime").value;
          const personalSeed = document.getElementById("personalSeed").value === "true";
          const body = {
            person,
            question_time: qtime,
            tz: person.tz,
            personal_seed: personalSeed
          };
          const data = await postJSON("/divine?pretty_cn=true", body);
          renderSimpleCard("out-divine", data.title, data.summary);
        } catch(e) { setErr("out-divine", e); }
      }

      async function runDailyFortune() {
        try {
          const person = getPerson();
          saveCurrentArchive(false);
          setLoading("out-daily", "正在测算今日运势…");
          const day = document.getElementById("fday").value;
          const body = {
            person,
            day: day ? day : null,
            tz: person.tz
          };
          const data = await postJSON("/daily-fortune?pretty_cn=true", body);
          renderDailyResult(data);
        } catch(e) { setErr("out-daily", e); }
      }
    </script>
  </body>
</html>
""".strip()
    return HTMLResponse(content=html)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/client-context")
def client_context(request: Request) -> dict[str, str]:
    return {"client_ip": _client_ip(request)}


@app.get("/ai-status")
def ai_status() -> dict[str, object]:
    cfg = ai_config_from_env()
    provider_label = "豆包（火山引擎 Ark）" if "volces.com" in cfg.base_url else "OpenAI 兼容服务"
    return {
        "configured": bool(cfg.api_key),
        "enabled": cfg.enabled,
        "base_url": cfg.base_url,
        "model": cfg.model,
        "provider_label": provider_label,
    }


@app.post("/ai-probe")
def ai_probe(request: Request, person: PersonProfile | None = None, model: str | None = None) -> dict[str, str]:
    try:
        _consume_ai_quota(request, person)
        cfg = ai_config_from_env()
        cfg.enabled = True
        if model:
            cfg.model = model
        from .openai_compat import generate_ai_text

        res = generate_ai_text(prompt="请只回复“连接正常”。", ai=cfg)
        return {"message": f"连接成功。\n当前模型：{cfg.model}\n模型回复：{res.text.strip()}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/bazi")
def api_bazi(person: PersonProfile, pretty_cn: bool = False):
    try:
        chart = build_bazi_chart(person)
        if not pretty_cn:
            return chart
        return {
            "title": f"{person.name}的八字命盘",
            "summary": format_bazi_text(person.name, chart),
            "data": chart.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/wealth")
def api_wealth(
    request: Request,
    person: PersonProfile,
    ai: bool = False,
    model: str | None = None,
    pretty_cn: bool = False,
):
    try:
        cfg: AiConfig | None = None
        if ai:
            _consume_ai_quota(request, person)
            cfg = ai_config_from_env()
            cfg.enabled = True
            if model:
                cfg.model = model
        report = build_wealth_report(person, ai=cfg)
        if not pretty_cn:
            return report
        return {
            "title": f"{person.name}的财运结构简报",
            "summary": format_wealth_text(person.name, report),
            "data": report.model_dump(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/select-date")
def api_select_date(req: DateSelectRequest, pretty_cn: bool = False):
    try:
        resp = select_dates(req)
        if not pretty_cn:
            return resp

        extra_conditions: list[str] = []
        if req.house_orientation:
            extra_conditions.append(f"房屋坐向/朝向：{req.house_orientation}（已记录，当前版本暂未计入评分）")
        if req.door_orientation:
            extra_conditions.append(f"入户门朝向：{req.door_orientation}（已记录，当前版本暂未计入评分）")
        if req.house_owner_name:
            extra_conditions.append(f"宅主姓名：{req.house_owner_name}（已记录）")
        if req.house_owner_birth:
            extra_conditions.append(f"宅主生辰：{req.house_owner_birth}（已记录，当前版本暂未单独起盘联算）")
        if req.co_resident_notes:
            extra_conditions.append(f"同住成员：{req.co_resident_notes}（已记录，当前版本暂未多人联算）")
        if req.move_time_window:
            extra_conditions.append(f"计划入宅时段：{req.move_time_window}（已记录，当前版本暂未细算时辰）")

        candidates_cn = []
        for c in resp.candidates:
            cd = c.model_dump()
            d = c.day
            candidates_cn.append(
                {
                    "日期": d.isoformat(),
                    "星期": weekday_cn(d),
                    "评分": c.score,
                    "适合": [purpose_cn(x) for x in c.good_for],
                    "不适合": [purpose_cn(x) for x in c.bad_for],
                    "理由": c.reasons,
                    "提醒": c.warnings,
                    "解析": summarize_candidate(purpose=req.purpose, candidate=cd),
                    "raw": cd,
                }
            )

        return {
            "目的": purpose_cn(req.purpose),
            "流派": school_cn(req.school),
            "开始日期": resp.start.isoformat(),
            "结束日期": resp.end.isoformat(),
            "搜索天数": resp.days,
            "补充条件": extra_conditions,
            "候选日": candidates_cn,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/divine")
def api_divine(req: DivineRequest, pretty_cn: bool = False):
    try:
        res = meihua_divination(
            person=req.person,
            question_dt=req.question_time,
            tz=req.tz,
            personal_seed=bool(req.person) and req.personal_seed,
        )
        parsed = res.to_dict()
        if not pretty_cn:
            return parsed
        display_name = req.person.name if req.person else "本次"
        return {
            "title": f"{display_name}的起卦结果",
            "summary": format_divination_text(display_name, parsed),
            "data": parsed,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/daily-fortune")
def api_daily_fortune(req: DailyFortuneRequest, pretty_cn: bool = False):
    try:
        resp = daily_fortune(req)
        if not pretty_cn:
            return resp
        return {
            "title": f"{req.person.name}的个人运势",
            "summary": format_daily_fortune_text(req.person.name, resp),
            "data": resp.model_dump(),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def main() -> None:
    host = os.getenv("GOSUAN_API_HOST", "127.0.0.1")
    port = int(os.getenv("GOSUAN_API_PORT", "8000"))
    uvicorn.run("gosuan.api:app", host=host, port=port, reload=False)

