from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class Gender(str, Enum):
    male = "male"
    female = "female"


class Purpose(str, Enum):
    move = "move"  # 搬迁/入宅
    construction = "construction"  # 动工/开工/装修
    opening = "opening"  # 开业/开张
    wedding = "wedding"  # 婚嫁


class DateSchool(str, Enum):
    best_fit = "best_fit"  # 默认：黄历宜忌 + 建除十二神 + 冲破硬禁忌 + 解释性评分
    almanac = "almanac"  # 仅黄历宜忌（通胜取法）
    jianchu = "jianchu"  # 仅建除十二神（结构性择日）
    strict = "strict"  # 更严格：必须命中“宜”且建除为强吉类，且避冲破


class PersonProfile(BaseModel):
    name: str = Field(..., description="姓名/称呼")
    gender: Gender = Field(..., description="性别（用于部分流派顺逆排盘等；此项目先保留字段）")
    birth_dt: datetime = Field(..., description="出生时间（带时分）")
    tz: str = Field("Asia/Shanghai", description="时区 IANA 名称，如 Asia/Shanghai")
    location: Optional[str] = Field(None, description="出生地或常住地（择日可用于你后续扩展地理规则）")


class BaziPillar(BaseModel):
    stem: str
    branch: str


class BaziChart(BaseModel):
    year: BaziPillar
    month: BaziPillar
    day: BaziPillar
    hour: BaziPillar
    day_master: str = Field(..., description="日主（天干）")
    wuxing_counts: dict[str, int] = Field(
        default_factory=dict, description="五行统计（木火土金水）"
    )
    shishen: dict[str, str] = Field(
        default_factory=dict,
        description="十神映射（针对年/月/时天干相对于日主：比劫/食伤/财/官杀/印）",
    )
    raw: dict[str, Any] = Field(default_factory=dict, description="底层库原始信息（可追溯）")


class WealthReport(BaseModel):
    overview: str
    structure: dict[str, Any] = Field(default_factory=dict)
    suggestions: list[str] = Field(default_factory=list)
    cautions: list[str] = Field(default_factory=list)
    ai_text: Optional[str] = None


class DateCandidate(BaseModel):
    day: date
    score: float
    good_for: list[Purpose] = Field(default_factory=list)
    bad_for: list[Purpose] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class DateSelectRequest(BaseModel):
    person: PersonProfile
    purpose: Purpose
    school: DateSchool = Field(DateSchool.best_fit, description="择日流派/算法组合")
    house_orientation: Optional[str] = Field(None, description="房屋坐向/朝向，如坐北朝南")
    door_orientation: Optional[str] = Field(None, description="入户门朝向，如东南")
    house_owner_name: Optional[str] = Field(None, description="宅主姓名")
    house_owner_birth: Optional[str] = Field(None, description="宅主生辰，当前先保留原始文本")
    co_resident_notes: Optional[str] = Field(None, description="同住成员信息/备注")
    move_time_window: Optional[str] = Field(None, description="计划入宅时段，如上午或 9:00-11:00")
    start: date
    end: Optional[date] = Field(
        None,
        description="结束日期（包含）。若提供 end，则优先使用 start~end 计算搜索范围；否则使用 days。",
    )
    days: int = Field(60, ge=1, le=366, description="搜索天数（当 end 未提供时生效）")
    limit: int = Field(10, ge=1, le=50)
    prefer_weekend: bool = False
    avoid_weekend: bool = False
    exclude_dates: list[date] = Field(default_factory=list, description="排除的日期列表（ISO 日期）")
    must_hit_yi: bool = Field(
        False, description="若为 True，则必须命中黄历“宜”的目的关键词，否则直接剔除"
    )
    min_score: float = Field(0, description="最低得分阈值（低于则剔除）")


class DateSelectResponse(BaseModel):
    purpose: Purpose
    start: date
    end: date
    days: int
    candidates: list[DateCandidate]


class AiConfig(BaseModel):
    enabled: bool = False
    base_url: str = "https://openrouter.ai/api/v1"
    api_key: str = ""
    model: str = "openrouter/free"
    timeout_s: float = 30.0
    extra_headers: dict[str, str] = Field(default_factory=dict)
    temperature: float = 0.7
    max_output_tokens: int = 900


class AiResult(BaseModel):
    text: str
    raw: dict[str, Any] = Field(default_factory=dict)


class DivineRequest(BaseModel):
    person: Optional[PersonProfile] = Field(
        None, description="个人信息（提供则启用个人种子，使起卦更贴合个人）"
    )
    question_time: datetime = Field(..., description="问事/起卦时间")
    tz: str = Field("Asia/Shanghai", description="起卦时区")
    personal_seed: bool = Field(True, description="是否启用个人种子（需 person 非空）")


class DivineResponse(BaseModel):
    upper: dict[str, Any]
    lower: dict[str, Any]
    moving_line: int
    method: str
    seed_detail: dict[str, Any]


class DailyFortuneRequest(BaseModel):
    person: PersonProfile
    day: Optional[date] = Field(None, description="要测算的日期（默认：按 tz 取今天）")
    tz: str = Field("Asia/Shanghai", description="用于确定“今天”的时区")


class DailyFortuneResponse(BaseModel):
    day: date
    tz: str
    zodiac: str
    day_ganzhi: str
    day_chong_zodiac: Optional[str] = None
    jianchu_12: str
    yi: list[str] = Field(default_factory=list)
    ji: list[str] = Field(default_factory=list)
    good: list[str] = Field(default_factory=list, description="个人今日更适合做的事（可执行表达）")
    bad: list[str] = Field(default_factory=list, description="个人今日不太适合做的事（可执行表达）")
    go_directions: list[str] = Field(default_factory=list, description="适合去的方向/方位")
    avoid_directions: list[str] = Field(default_factory=list, description="不适合去的方向/方位")
    lucky_numbers: list[int] = Field(default_factory=list, description="当天幸运数字（娱乐向）")
    lucky_direction: Optional[str] = Field(None, description="当天幸运方位（娱乐向）")
    lottery_numbers: list[int] = Field(default_factory=list, description="当天彩票娱乐号（不具预测保证）")
    lottery_recommendations: dict[str, list[int]] = Field(default_factory=dict, description="分彩种娱乐号")
    stock_market_level: Optional[str] = Field(None, description="市场观察等级（非投资建议）")
    stock_preferred_digits: list[int] = Field(default_factory=list, description="当日偏好数字（娱乐化观察）")
    stock_avoid_digits: list[int] = Field(default_factory=list, description="当日避忌数字（娱乐化观察）")
    stock_theme_keywords: list[str] = Field(default_factory=list, description="可优先观察的板块/主题词")
    stock_avoid_keywords: list[str] = Field(default_factory=list, description="尽量回避的板块/主题词")
    stock_code_hints: list[str] = Field(default_factory=list, description="代码形态提示（娱乐化观察）")
    stock_market_note: Optional[str] = Field(None, description="市场观察提示（非投资建议）")
    notes: list[str] = Field(default_factory=list, description="解释与注意事项")
    raw: dict[str, Any] = Field(default_factory=dict, description="黄历原始字段（可追溯）")

