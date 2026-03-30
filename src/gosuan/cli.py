from __future__ import annotations

import argparse
import json
import os
from datetime import date, datetime

from dateutil import parser as dt_parser

from .bazi import build_bazi_chart
from .daily_fortune import daily_fortune
from .date_select import select_dates
from .format_cn import (
    format_bazi_text,
    format_daily_fortune_text,
    format_divination_text,
    format_select_date_text,
    format_wealth_text,
    summarize_candidate,
    weekday_cn,
)
from .meihua import meihua_divination
from .models import AiConfig, DailyFortuneRequest, DateSchool, DateSelectRequest, Gender, PersonProfile, Purpose
from .openai_compat import ai_config_from_env
from .wealth import build_wealth_report


def _parse_date(s: str) -> date:
    return date.fromisoformat(s)


def _parse_birth(s: str) -> datetime:
    # 支持 "1995-08-17 14:30" / ISO8601 等
    return dt_parser.parse(s)


def _person_from_args(args: argparse.Namespace) -> PersonProfile:
    return PersonProfile(
        name=args.name,
        gender=Gender(args.gender),
        birth_dt=_parse_birth(args.birth),
        tz=args.tz,
        location=getattr(args, "location", None),
    )


def cmd_bazi(args: argparse.Namespace) -> int:
    person = _person_from_args(args)
    chart = build_bazi_chart(person)
    if args.json:
        print(json.dumps(chart.model_dump(), ensure_ascii=False, indent=2))
    else:
        print(format_bazi_text(person.name, chart))
    return 0


def cmd_wealth(args: argparse.Namespace) -> int:
    person = _person_from_args(args)
    ai: AiConfig | None = None
    if args.ai:
        cfg = ai_config_from_env()
        cfg.enabled = True
        if args.model:
            cfg.model = args.model
        if args.base_url:
            cfg.base_url = args.base_url
        if args.api_key:
            cfg.api_key = args.api_key
        ai = cfg

    report = build_wealth_report(person, ai=ai)
    if args.json:
        print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    else:
        print(format_wealth_text(person.name, report))
    return 0


def cmd_select_date(args: argparse.Namespace) -> int:
    person = _person_from_args(args)
    if args.best:
        args.limit = 1
    req = DateSelectRequest(
        person=person,
        purpose=Purpose(args.purpose),
        school=DateSchool(args.school),
        start=_parse_date(args.start),
        end=_parse_date(args.end) if args.end else None,
        days=args.days,
        limit=args.limit,
        prefer_weekend=args.prefer_weekend,
        avoid_weekend=args.avoid_weekend,
        exclude_dates=[_parse_date(x) for x in (args.exclude_date or [])],
        must_hit_yi=args.must_hit_yi,
        min_score=args.min_score,
    )
    resp = select_dates(req)
    if args.json:
        print(json.dumps(resp.model_dump(), ensure_ascii=False, indent=2))
    else:
        payload = {
            "开始日期": resp.start.isoformat(),
            "结束日期": resp.end.isoformat(),
            "候选日": [
                {
                    "日期": c.day.isoformat(),
                    "星期": weekday_cn(c.day),
                    "评分": c.score,
                    "理由": c.reasons,
                    "提醒": c.warnings,
                    "解析": summarize_candidate(purpose=req.purpose, candidate=c.model_dump()),
                }
                for c in resp.candidates
            ],
        }
        print(format_select_date_text(name=person.name, purpose=req.purpose, school=req.school, payload=payload))
    return 0


def cmd_divine(args: argparse.Namespace) -> int:
    person = _person_from_args(args) if args.with_person else None
    qdt = _parse_birth(args.question_time)
    # 默认：只要传了 --with-person，就启用个人种子（更贴合个人）
    # 若未传 --with-person，则不启用个人种子
    personal_seed = bool(person)
    res = meihua_divination(
        person=person,
        question_dt=qdt,
        tz=args.tz,
        personal_seed=personal_seed,
    )
    if args.json:
        print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(format_divination_text(args.name, res.to_dict()))
    return 0


def cmd_daily_fortune(args: argparse.Namespace) -> int:
    person = _person_from_args(args)
    req = DailyFortuneRequest(
        person=person,
        day=_parse_date(args.day) if args.day else None,
        tz=args.tz,
    )
    resp = daily_fortune(req)
    if args.json:
        print(json.dumps(resp.model_dump(), ensure_ascii=False, indent=2))
    else:
        print(format_daily_fortune_text(person.name, resp))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gosuan", description="个人玄学算卦/财运/择日工具")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--name", required=True)
        sp.add_argument("--gender", required=True, choices=[g.value for g in Gender])
        sp.add_argument("--birth", required=True, help='如 "1995-08-17 14:30" 或 ISO8601')
        sp.add_argument("--tz", default=os.getenv("GOSUAN_TZ", "Asia/Shanghai"))
        sp.add_argument("--location", default=None)
        sp.add_argument("--json", action="store_true", help="输出原始 JSON，便于脚本或二次处理")

    sp1 = sub.add_parser("bazi", help="输出八字命盘 JSON")
    add_common(sp1)
    sp1.set_defaults(func=cmd_bazi)

    sp2 = sub.add_parser("wealth", help="输出财运结构解读 JSON（可选 AI 文案）")
    add_common(sp2)
    sp2.add_argument("--ai", action="store_true", help="启用 AI 文案生成（OpenAI 兼容）")
    sp2.add_argument("--base-url", default=None, help="覆盖 GOSUAN_AI_BASE_URL")
    sp2.add_argument("--api-key", default=None, help="覆盖 GOSUAN_AI_API_KEY")
    sp2.add_argument("--model", default=None, help="覆盖 GOSUAN_AI_MODEL")
    sp2.set_defaults(func=cmd_wealth)

    sp3 = sub.add_parser("select-date", help="择日：搬迁/动工等")
    add_common(sp3)
    sp3.add_argument("--purpose", required=True, choices=[p.value for p in Purpose])
    sp3.add_argument(
        "--school",
        default=DateSchool.best_fit.value,
        choices=[s.value for s in DateSchool],
        help="择日流派/算法组合",
    )
    sp3.add_argument("--start", required=True, help="ISO 日期，如 2026-04-01")
    sp3.add_argument("--end", default=None, help="ISO 日期（包含），如 2026-05-31（提供后忽略 days）")
    sp3.add_argument("--days", type=int, default=60)
    sp3.add_argument("--limit", type=int, default=10)
    sp3.add_argument("--prefer-weekend", action="store_true")
    sp3.add_argument("--avoid-weekend", action="store_true")
    sp3.add_argument("--exclude-date", action="append", default=None, help="排除日期（可重复传）")
    sp3.add_argument("--must-hit-yi", action="store_true", help="必须命中黄历“宜”的目的关键词，否则剔除")
    sp3.add_argument("--min-score", type=float, default=0, help="最低得分阈值（低于则剔除）")
    sp3.add_argument("--best", action="store_true", help="只返回时间段内最合适的 1 天（等价于 limit=1）")
    sp3.set_defaults(func=cmd_select_date)

    sp4 = sub.add_parser("divine", help="算卦（梅花易数起卦）：输出上卦/下卦/动爻等可复核字段")
    add_common(sp4)
    sp4.add_argument("--question-time", required=True, help='问事/起卦时间，如 "2026-04-01 09:30"')
    sp4.add_argument("--with-person", action="store_true", help="将个人出生信息作为加权种子（更贴合个人）")
    # 预留兼容：个人种子目前由 --with-person 控制，后续若你需要“禁用个人种子”再扩展参数
    sp4.set_defaults(func=cmd_divine)

    sp5 = sub.add_parser("daily-fortune", help="测算某天个人运势：宜忌/适合做什么/方位建议")
    add_common(sp5)
    sp5.add_argument("--day", default=None, help="ISO 日期，如 2026-04-01（不传则按 tz 取今天）")
    sp5.set_defaults(func=cmd_daily_fortune)

    return p


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    code = args.func(args)
    raise SystemExit(code)


if __name__ == "__main__":
    main()

