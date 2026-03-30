from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from .models import PersonProfile


TRIGRAMS = [
    ("乾", "☰"),  # 1
    ("兑", "☱"),  # 2
    ("离", "☲"),  # 3
    ("震", "☳"),  # 4
    ("巽", "☴"),  # 5
    ("坎", "☵"),  # 6
    ("艮", "☶"),  # 7
    ("坤", "☷"),  # 8
]

# 八卦五行（常用口径）
TRIGRAM_ELEMENT = {
    "乾": "金",
    "兑": "金",
    "离": "火",
    "震": "木",
    "巽": "木",
    "坎": "水",
    "艮": "土",
    "坤": "土",
}


@dataclass(frozen=True)
class MeiHuaResult:
    # 1..8
    upper_index: int
    lower_index: int
    # 1..6
    moving_line: int
    # 卦名/符号
    upper_name: str
    lower_name: str
    upper_symbol: str
    lower_symbol: str
    upper_element: str
    lower_element: str
    # 简洁可解释字段
    method: str
    seed_detail: dict[str, int]

    def to_dict(self) -> dict:
        return {
            "upper": {
                "index": self.upper_index,
                "name": self.upper_name,
                "symbol": self.upper_symbol,
                "element": self.upper_element,
            },
            "lower": {
                "index": self.lower_index,
                "name": self.lower_name,
                "symbol": self.lower_symbol,
                "element": self.lower_element,
            },
            "moving_line": self.moving_line,
            "method": self.method,
            "seed_detail": self.seed_detail,
        }


def _mod1(n: int, mod: int) -> int:
    r = n % mod
    return mod if r == 0 else r


def meihua_divination(
    *,
    person: PersonProfile | None,
    question_dt: datetime,
    tz: str = "Asia/Shanghai",
    personal_seed: bool = True,
) -> MeiHuaResult:
    """
    梅花易数起卦（确定性、可复核）。

    通行取法之一（时间起卦）：
    - 上卦 = (月 + 日 + 时 + 个人种子) mod 8
    - 下卦 = (月 + 日 + 时 + 分 + 个人种子) mod 8
    - 动爻 = (月 + 日 + 时 + 分 + 个人种子) mod 6

    个人种子（personal_seed=True 且 person 提供）：
    - 取出生年月日时分的“月+日+时+分”作为轻量加权，让结果更“对个人”而非通用随机。
    """
    z = ZoneInfo(tz)
    q = question_dt
    if q.tzinfo is None:
        q = q.replace(tzinfo=z)
    else:
        q = q.astimezone(z)

    base = q.month + q.day + q.hour
    base2 = q.month + q.day + q.hour + q.minute

    seed = 0
    seed_detail = {
        "q_month": q.month,
        "q_day": q.day,
        "q_hour": q.hour,
        "q_minute": q.minute,
    }
    method = "梅花易数-时间起卦"

    if personal_seed and person is not None:
        b = person.birth_dt
        if b.tzinfo is None:
            b = b.replace(tzinfo=ZoneInfo(person.tz))
        else:
            b = b.astimezone(ZoneInfo(person.tz))
        seed = b.month + b.day + b.hour + b.minute
        seed_detail.update(
            {
                "b_month": b.month,
                "b_day": b.day,
                "b_hour": b.hour,
                "b_minute": b.minute,
                "personal_seed": seed,
            }
        )
        method += "+个人种子"

    upper_index = _mod1(base + seed, 8)
    lower_index = _mod1(base2 + seed, 8)
    moving_line = _mod1(base2 + seed, 6)

    upper_name, upper_symbol = TRIGRAMS[upper_index - 1]
    lower_name, lower_symbol = TRIGRAMS[lower_index - 1]

    return MeiHuaResult(
        upper_index=upper_index,
        lower_index=lower_index,
        moving_line=moving_line,
        upper_name=upper_name,
        lower_name=lower_name,
        upper_symbol=upper_symbol,
        lower_symbol=lower_symbol,
        upper_element=TRIGRAM_ELEMENT[upper_name],
        lower_element=TRIGRAM_ELEMENT[lower_name],
        method=method,
        seed_detail=seed_detail,
    )

