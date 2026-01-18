"""
User Investment Preferences Model

Defines user investment preferences for personalized recommendations.
"""
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class RiskLevel(str, Enum):
    """用户风险偏好等级"""
    CONSERVATIVE = "conservative"  # 保守型 - 追求本金安全，接受较低收益
    MODERATE = "moderate"  # 稳健型 - 平衡风险和收益
    AGGRESSIVE = "aggressive"  # 积进型 - 追求较高收益，接受中等风险
    SPECULATIVE = "speculative"  # 投机型 - 追求高收益，接受高风险


class InvestmentHorizon(str, Enum):
    """投资期限"""
    SHORT_TERM = "short_term"  # 短期 - 7-30天
    MEDIUM_TERM = "medium_term"  # 中期 - 1-6个月
    LONG_TERM = "long_term"  # 长期 - 6个月以上


class InvestmentGoal(str, Enum):
    """投资目标"""
    CAPITAL_PRESERVATION = "capital_preservation"  # 保本 - 追求本金安全
    STEADY_INCOME = "steady_income"  # 稳定收益 - 追求稳定现金流
    CAPITAL_APPRECIATION = "capital_appreciation"  # 资本增值 - 长期增长
    SPECULATION = "speculation"  # 投机 - 短期高收益


class InvestmentStyle(str, Enum):
    """投资风格"""
    VALUE = "value"  # 价值投资 - 低估值、高股息
    GROWTH = "growth"  # 成长投资 - 高成长、高PE
    BLEND = "blend"  # 均衡 - 价值与成长平衡
    MOMENTUM = "momentum"  # 动量投资 - 追涨杀跌
    DIVIDEND = "dividend"  # 股息投资 - 高分红


class UserInvestmentPreferences:
    """用户投资偏好配置"""

    def __init__(
        self,
        # 基本风险设置
        risk_level: RiskLevel = RiskLevel.MODERATE,
        investment_horizon: InvestmentHorizon = InvestmentHorizon.MEDIUM_TERM,
        investment_goal: InvestmentGoal = InvestmentGoal.CAPITAL_APPRECIATION,
        investment_style: InvestmentStyle = InvestmentStyle.BLEND,

        # 资金与仓位
        total_capital: Optional[float] = None,  # 总投资金额
        max_single_position: float = 0.15,  # 单只标的最大仓位（15%）
        max_sector_position: float = 0.30,  # 单个行业最大仓位（30%）

        # 风险控制
        max_drawdown_tolerance: float = 0.20,  # 最大回撤容忍度（20%）
        stop_loss_percentage: float = 0.08,  # 止损比例（8%）
        take_profit_percentage: Optional[float] = None,  # 止盈比例（可选）

        # 选股偏好
        min_market_cap: Optional[float] = 5e9,  # 最小市值（50亿）
        max_market_cap: Optional[float] = None,  # 最大市值（不限）
        min_pe: Optional[float] = None,  # 最小PE
        max_pe: Optional[float] = None,  # 最大PE
        min_pb: Optional[float] = None,  # 最小PB
        max_pb: Optional[float] = None,  # 最大PB
        min_roe: Optional[float] = None,  # 最小ROE
        min_dividend_yield: Optional[float] = None,  # 最小股息率

        # 行业偏好
        preferred_sectors: Optional[List[str]] = None,  # 偏好行业
        excluded_sectors: Optional[List[str]] = None,  # 排除行业
        preferred_themes: Optional[List[str]] = None,  # 投资主题（新能源、AI等）

        # 基金偏好
        preferred_fund_types: Optional[List[str]] = None,  # 偏好基金类型
        excluded_fund_types: Optional[List[str]] = None,  # 排除基金类型
        min_fund_scale: Optional[float] = 1e8,  # 基金最小规模（1亿）
        max_fund_management_fee: float = 0.015,  # 最大管理费率（1.5%）

        # 推荐数量
        stock_recommendation_count: int = 8,  # 推荐股票数量
        fund_recommendation_count: int = 5,  # 推荐基金数量

        # 其他偏好
        avoid_st_stocks: bool = True,  # 排除ST股票
        avoid_new_stocks: bool = True,  # 排除次新股（上市<1年）
        require_profitable: bool = True,  # 要求盈利（PE>0）
        min_liquidity: Optional[float] = 1e8,  # 最小日均成交额（1亿）

        # 元数据
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
    ):
        self.risk_level = risk_level
        self.investment_horizon = investment_horizon
        self.investment_goal = investment_goal
        self.investment_style = investment_style

        self.total_capital = total_capital
        self.max_single_position = max_single_position
        self.max_sector_position = max_sector_position

        self.max_drawdown_tolerance = max_drawdown_tolerance
        self.stop_loss_percentage = stop_loss_percentage
        self.take_profit_percentage = take_profit_percentage

        self.min_market_cap = min_market_cap
        self.max_market_cap = max_market_cap
        self.min_pe = min_pe
        self.max_pe = max_pe
        self.min_pb = min_pb
        self.max_pb = max_pb
        self.min_roe = min_roe
        self.min_dividend_yield = min_dividend_yield

        self.preferred_sectors = preferred_sectors or []
        self.excluded_sectors = excluded_sectors or []
        self.preferred_themes = preferred_themes or []

        self.preferred_fund_types = preferred_fund_types or []
        self.excluded_fund_types = excluded_fund_types or []
        self.min_fund_scale = min_fund_scale
        self.max_fund_management_fee = max_fund_management_fee

        self.stock_recommendation_count = stock_recommendation_count
        self.fund_recommendation_count = fund_recommendation_count

        self.avoid_st_stocks = avoid_st_stocks
        self.avoid_new_stocks = avoid_new_stocks
        self.require_profitable = require_profitable
        self.min_liquidity = min_liquidity

        self.created_at = created_at or datetime.now()
        self.updated_at = updated_at or datetime.now()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "risk_level": self.risk_level.value if isinstance(self.risk_level, RiskLevel) else self.risk_level,
            "investment_horizon": self.investment_horizon.value if isinstance(self.investment_horizon, InvestmentHorizon) else self.investment_horizon,
            "investment_goal": self.investment_goal.value if isinstance(self.investment_goal, InvestmentGoal) else self.investment_goal,
            "investment_style": self.investment_style.value if isinstance(self.investment_style, InvestmentStyle) else self.investment_style,
            "total_capital": self.total_capital,
            "max_single_position": self.max_single_position,
            "max_sector_position": self.max_sector_position,
            "max_drawdown_tolerance": self.max_drawdown_tolerance,
            "stop_loss_percentage": self.stop_loss_percentage,
            "take_profit_percentage": self.take_profit_percentage,
            "min_market_cap": self.min_market_cap,
            "max_market_cap": self.max_market_cap,
            "min_pe": self.min_pe,
            "max_pe": self.max_pe,
            "min_pb": self.min_pb,
            "max_pb": self.max_pb,
            "min_roe": self.min_roe,
            "min_dividend_yield": self.min_dividend_yield,
            "preferred_sectors": self.preferred_sectors,
            "excluded_sectors": self.excluded_sectors,
            "preferred_themes": self.preferred_themes,
            "preferred_fund_types": self.preferred_fund_types,
            "excluded_fund_types": self.excluded_fund_types,
            "min_fund_scale": self.min_fund_scale,
            "max_fund_management_fee": self.max_fund_management_fee,
            "stock_recommendation_count": self.stock_recommendation_count,
            "fund_recommendation_count": self.fund_recommendation_count,
            "avoid_st_stocks": self.avoid_st_stocks,
            "avoid_new_stocks": self.avoid_new_stocks,
            "require_profitable": self.require_profitable,
            "min_liquidity": self.min_liquidity,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserInvestmentPreferences":
        """Create from dictionary."""
        # Convert string enums back to enum objects
        if "risk_level" in data and isinstance(data["risk_level"], str):
            data["risk_level"] = RiskLevel(data["risk_level"])
        if "investment_horizon" in data and isinstance(data["investment_horizon"], str):
            data["investment_horizon"] = InvestmentHorizon(data["investment_horizon"])
        if "investment_goal" in data and isinstance(data["investment_goal"], str):
            data["investment_goal"] = InvestmentGoal(data["investment_goal"])
        if "investment_style" in data and isinstance(data["investment_style"], str):
            data["investment_style"] = InvestmentStyle(data["investment_style"])

        # Convert datetime strings back to datetime objects
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])

        return cls(**data)

    def get_risk_adjusted_parameters(self) -> Dict[str, Any]:
        """
        根据风险等级返回推荐的筛选参数。

        Returns:
            Dict containing recommended screening parameters
        """
        params = {}

        if self.risk_level == RiskLevel.CONSERVATIVE:
            params.update({
                "min_market_cap": max(self.min_market_cap or 0, 5e10),  # 至少500亿
                "max_pe": min(self.max_pe or 30, 30),  # PE不超过30
                "max_volatility": 0.15,  # 低波动
                "min_dividend_yield": 0.02,  # 至少2%股息率
                "preferred_sectors": ["银行", "公用事业", "消费", "医药"],
            })
        elif self.risk_level == RiskLevel.MODERATE:
            params.update({
                "min_market_cap": max(self.min_market_cap or 0, 2e10),  # 至少200亿
                "max_pe": min(self.max_pe or 50, 50),
                "max_volatility": 0.25,
            })
        elif self.risk_level == RiskLevel.AGGRESSIVE:
            params.update({
                "min_market_cap": max(self.min_market_cap or 0, 5e9),  # 至少50亿
                "max_pe": min(self.max_pe or 100, 100),
                "max_volatility": 0.40,
                "preferred_sectors": ["科技", "新能源", "消费电子"],
            })
        else:  # SPECULATIVE
            params.update({
                "min_market_cap": self.min_market_cap or 1e9,  # 至少10亿
                "max_volatility": 1.0,  # 接受高波动
            })

        return params


# 预定义的风险配置模板
RISK_LEVEL_PRESETS = {
    RiskLevel.CONSERVATIVE: UserInvestmentPreferences(
        risk_level=RiskLevel.CONSERVATIVE,
        investment_horizon=InvestmentHorizon.LONG_TERM,
        investment_goal=InvestmentGoal.STEADY_INCOME,
        investment_style=InvestmentStyle.DIVIDEND,
        max_single_position=0.10,
        max_drawdown_tolerance=0.10,
        stop_loss_percentage=0.05,
        min_market_cap=5e10,
        max_pe=30,
        min_dividend_yield=0.02,
        stock_recommendation_count=5,
        fund_recommendation_count=8,
    ),
    RiskLevel.MODERATE: UserInvestmentPreferences(
        risk_level=RiskLevel.MODERATE,
        investment_horizon=InvestmentHorizon.MEDIUM_TERM,
        investment_goal=InvestmentGoal.CAPITAL_APPRECIATION,
        investment_style=InvestmentStyle.BLEND,
        max_single_position=0.15,
        max_drawdown_tolerance=0.20,
        stop_loss_percentage=0.08,
        min_market_cap=2e10,
        max_pe=50,
        stock_recommendation_count=8,
        fund_recommendation_count=5,
    ),
    RiskLevel.AGGRESSIVE: UserInvestmentPreferences(
        risk_level=RiskLevel.AGGRESSIVE,
        investment_horizon=InvestmentHorizon.SHORT_TERM,
        investment_goal=InvestmentGoal.CAPITAL_APPRECIATION,
        investment_style=InvestmentStyle.GROWTH,
        max_single_position=0.20,
        max_drawdown_tolerance=0.30,
        stop_loss_percentage=0.10,
        min_market_cap=5e9,
        max_pe=100,
        stock_recommendation_count=10,
        fund_recommendation_count=3,
    ),
    RiskLevel.SPECULATIVE: UserInvestmentPreferences(
        risk_level=RiskLevel.SPECULATIVE,
        investment_horizon=InvestmentHorizon.SHORT_TERM,
        investment_goal=InvestmentGoal.SPECULATION,
        investment_style=InvestmentStyle.MOMENTUM,
        max_single_position=0.25,
        max_drawdown_tolerance=0.50,
        stop_loss_percentage=0.15,
        min_market_cap=1e9,
        stock_recommendation_count=15,
        fund_recommendation_count=2,
        avoid_new_stocks=False,
    ),
}
