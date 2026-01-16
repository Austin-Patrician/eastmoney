"""
Fund Screeners - Short-term and Long-term fund screening implementations.
"""
import akshare as ak
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime
from .base_screener import BaseScreener


class ShortTermFundScreener(BaseScreener):
    """
    Short-term fund screener (7+ days holding period).

    Focuses on:
    - Recent performance (近期业绩) - 35% weight
    - Holdings momentum (持仓热度) - 25% weight
    - Size & liquidity (规模流动性) - 20% weight
    - Manager reputation (基金经理) - 20% weight
    """

    @property
    def screener_type(self) -> str:
        return "short_term_fund"

    @property
    def default_limit(self) -> int:
        return 30

    def collect_raw_data(self) -> Dict[str, Any]:
        """Collect data from AkShare APIs - 只获取TOP基金."""
        data = {}

        # 1. 获取股票型基金（只取近1周排名前100）
        try:
            df_stock = ak.fund_open_fund_rank_em(symbol="股票型")
            if df_stock is not None and not df_stock.empty:
                # 按近1周排序，取前100
                if '近1周' in df_stock.columns:
                    df_stock['近1周_num'] = pd.to_numeric(df_stock['近1周'], errors='coerce')
                    df_stock = df_stock.sort_values('近1周_num', ascending=False).head(100)
                df_stock['fund_type'] = '股票型'
                data['fund_rank_stock'] = df_stock
                print(f"  ✓ 获取股票型基金TOP100: {len(df_stock)} 只")
        except Exception as e:
            print(f"  ✗ 获取股票型基金失败: {e}")
            data['fund_rank_stock'] = pd.DataFrame()

        # 2. 获取混合型基金（只取近1周排名前100）
        try:
            df_mixed = ak.fund_open_fund_rank_em(symbol="混合型")
            if df_mixed is not None and not df_mixed.empty:
                if '近1周' in df_mixed.columns:
                    df_mixed['近1周_num'] = pd.to_numeric(df_mixed['近1周'], errors='coerce')
                    df_mixed = df_mixed.sort_values('近1周_num', ascending=False).head(100)
                df_mixed['fund_type'] = '混合型'
                data['fund_rank_mixed'] = df_mixed
                print(f"  ✓ 获取混合型基金TOP100: {len(df_mixed)} 只")
        except Exception as e:
            print(f"  ✗ 获取混合型基金失败: {e}")
            data['fund_rank_mixed'] = pd.DataFrame()

        # 3. 获取ETF行情（按成交额排序取前50）
        try:
            df_etf = ak.fund_etf_spot_em()
            if df_etf is not None and not df_etf.empty:
                if '成交额' in df_etf.columns:
                    df_etf['成交额_num'] = pd.to_numeric(df_etf['成交额'], errors='coerce')
                    df_etf = df_etf.sort_values('成交额_num', ascending=False).head(50)
                data['etf_spot'] = df_etf
                print(f"  ✓ 获取ETF成交额TOP50: {len(df_etf)} 只")
        except Exception as e:
            print(f"  ✗ 获取ETF行情失败: {e}")
            data['etf_spot'] = pd.DataFrame()

        return data

    def apply_filters(self, raw_data: Dict[str, Any]) -> List[Dict]:
        """Apply short-term filtering rules - 严格筛选."""
        candidates = []

        # Process open-end funds
        for key in ['fund_rank_stock', 'fund_rank_mixed']:
            df = raw_data.get(key, pd.DataFrame())
            if df.empty:
                continue

            for _, row in df.iterrows():
                try:
                    code = str(row.get('基金代码', '')).strip()
                    name = str(row.get('基金简称', ''))

                    # 基本排除
                    if '指数' in name and '增强' not in name:
                        continue
                    if 'QDII' in name:
                        continue
                    if 'C' in code[-1:]:  # 排除C类份额（费用结构不同）
                        continue

                    # 获取业绩指标
                    return_1w = self._safe_float(row.get('近1周'))
                    return_1m = self._safe_float(row.get('近1月'))
                    return_3m = self._safe_float(row.get('近3月'))
                    return_6m = self._safe_float(row.get('近6月'))
                    return_1y = self._safe_float(row.get('近1年'))

                    # ===== 严格筛选条件 =====

                    # 1. 必须有近期数据
                    if return_1w is None or return_1m is None:
                        continue

                    # 2. 近1周 > 0%（正收益）
                    if return_1w <= 0:
                        continue

                    # 3. 近1月 > 2%（有明显上涨趋势）
                    if return_1m <= 2:
                        continue

                    # 4. 近3月 > 0%（中期趋势向好）
                    if return_3m is not None and return_3m <= 0:
                        continue

                    candidate = {
                        'code': code,
                        'name': name,
                        'type': 'open_fund',
                        'fund_type': row.get('fund_type', ''),
                        'return_1w': return_1w,
                        'return_1m': return_1m,
                        'return_3m': return_3m,
                        'return_6m': return_6m,
                        'return_1y': return_1y,
                        'nav': self._safe_float(row.get('单位净值')),
                        'nav_date': str(row.get('日期', '')),
                    }

                    candidates.append(candidate)

                except Exception as e:
                    continue

        # Process ETFs - 更严格的筛选
        df_etf = raw_data.get('etf_spot', pd.DataFrame())
        if not df_etf.empty:
            for _, row in df_etf.iterrows():
                try:
                    code = str(row.get('代码', '')).strip()
                    name = str(row.get('名称', ''))

                    # 排除货币/债券ETF
                    if '货币' in name or '现金' in name or '债' in name:
                        continue

                    # 获取指标
                    price = self._safe_float(row.get('最新价'))
                    change_pct = self._safe_float(row.get('涨跌幅'))
                    turnover = self._safe_float(row.get('成交额'))

                    # ===== 严格筛选条件 =====

                    # 1. 成交额 > 1亿（高流动性）
                    if not turnover or turnover < 1e8:
                        continue

                    # 2. 必须有价格
                    if not price or price <= 0:
                        continue

                    # 3. 涨跌幅 > -2%（不追跌）
                    if change_pct is not None and change_pct < -2:
                        continue

                    candidate = {
                        'code': code,
                        'name': name,
                        'type': 'etf',
                        'fund_type': 'ETF',
                        'price': price,
                        'change_pct': change_pct,
                        'turnover': turnover,
                        'return_1w': change_pct,
                    }

                    candidates.append(candidate)

                except Exception as e:
                    continue

        print(f"  ✓ 严格筛选后: {len(candidates)} 只基金/ETF")
        return candidates

    def calculate_scores(self, candidates: List[Dict]) -> List[Dict]:
        """Calculate composite score for short-term funds."""
        if not candidates:
            return []

        # Separate open funds and ETFs for different scoring
        open_funds = [c for c in candidates if c.get('type') == 'open_fund']
        etfs = [c for c in candidates if c.get('type') == 'etf']

        # Score open funds
        if open_funds:
            returns_1w = [c.get('return_1w', 0) for c in open_funds if c.get('return_1w') is not None]
            returns_1m = [c.get('return_1m', 0) for c in open_funds if c.get('return_1m') is not None]

            max_1w = max(returns_1w) if returns_1w else 1
            min_1w = min(returns_1w) if returns_1w else 0
            max_1m = max(returns_1m) if returns_1m else 1
            min_1m = min(returns_1m) if returns_1m else 0

            for c in open_funds:
                score = 0

                # 1. Recent performance (35%)
                r1w = c.get('return_1w', 0) or 0
                r1m = c.get('return_1m', 0) or 0

                if max_1w != min_1w:
                    score_1w = (r1w - min_1w) / (max_1w - min_1w) * 17.5
                else:
                    score_1w = 8.75

                if max_1m != min_1m:
                    score_1m = (r1m - min_1m) / (max_1m - min_1m) * 17.5
                else:
                    score_1m = 8.75

                score += score_1w + score_1m

                # 2. Holdings momentum placeholder (25%)
                score += 12.5

                # 3. Size & liquidity placeholder (20%)
                score += 10

                # 4. Manager reputation placeholder (20%)
                score += 10

                c['score'] = round(score, 2)

        # Score ETFs
        if etfs:
            turnovers = [c.get('turnover', 0) for c in etfs if c.get('turnover')]
            changes = [c.get('change_pct', 0) for c in etfs if c.get('change_pct') is not None]

            max_turnover = max(turnovers) if turnovers else 1
            max_change = max(changes) if changes else 1
            min_change = min(changes) if changes else 0

            for c in etfs:
                score = 0

                # 1. Daily performance (35%)
                change = c.get('change_pct', 0) or 0
                if max_change != min_change:
                    score += (change - min_change) / (max_change - min_change) * 35
                else:
                    score += 17.5

                # 2. Liquidity (25%)
                turnover = c.get('turnover', 0) or 0
                if max_turnover > 0:
                    score += min(turnover / max_turnover, 1) * 25
                else:
                    score += 12.5

                # 3. Volume activity (20%)
                score += 10

                # 4. Market correlation (20%)
                score += 10

                c['score'] = round(score, 2)

        return candidates

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        if value is None or value == '' or value == '--':
            return None
        try:
            if isinstance(value, str):
                value = value.replace(',', '').replace('%', '')
            return float(value)
        except (ValueError, TypeError):
            return None


class LongTermFundScreener(BaseScreener):
    """
    Long-term fund screener (3+ months holding period).

    Focuses on:
    - Long-term performance (长期业绩) - 35% weight
    - Risk-adjusted return (风险调整收益) - 25% weight
    - Fund manager (基金经理) - 25% weight
    - Holdings quality (持仓质量) - 15% weight
    """

    @property
    def screener_type(self) -> str:
        return "long_term_fund"

    @property
    def default_limit(self) -> int:
        return 30

    def collect_raw_data(self) -> Dict[str, Any]:
        """Collect data from AkShare APIs - 只获取长期业绩TOP基金."""
        data = {}

        # 1. 获取股票型基金（按近1年排序，取前100）
        try:
            df_stock = ak.fund_open_fund_rank_em(symbol="股票型")
            if df_stock is not None and not df_stock.empty:
                if '近1年' in df_stock.columns:
                    df_stock['近1年_num'] = pd.to_numeric(df_stock['近1年'], errors='coerce')
                    df_stock = df_stock.sort_values('近1年_num', ascending=False).head(100)
                df_stock['fund_type'] = '股票型'
                data['fund_rank_stock'] = df_stock
                print(f"  ✓ 获取股票型基金近1年TOP100: {len(df_stock)} 只")
        except Exception as e:
            print(f"  ✗ 获取股票型基金失败: {e}")
            data['fund_rank_stock'] = pd.DataFrame()

        # 2. 获取混合型基金（按近1年排序，取前100）
        try:
            df_mixed = ak.fund_open_fund_rank_em(symbol="混合型")
            if df_mixed is not None and not df_mixed.empty:
                if '近1年' in df_mixed.columns:
                    df_mixed['近1年_num'] = pd.to_numeric(df_mixed['近1年'], errors='coerce')
                    df_mixed = df_mixed.sort_values('近1年_num', ascending=False).head(100)
                df_mixed['fund_type'] = '混合型'
                data['fund_rank_mixed'] = df_mixed
                print(f"  ✓ 获取混合型基金近1年TOP100: {len(df_mixed)} 只")
        except Exception as e:
            print(f"  ✗ 获取混合型基金失败: {e}")
            data['fund_rank_mixed'] = pd.DataFrame()

        # 3. 获取指数型基金（按近1年排序，取前50）
        try:
            df_index = ak.fund_open_fund_rank_em(symbol="指数型")
            if df_index is not None and not df_index.empty:
                if '近1年' in df_index.columns:
                    df_index['近1年_num'] = pd.to_numeric(df_index['近1年'], errors='coerce')
                    df_index = df_index.sort_values('近1年_num', ascending=False).head(50)
                df_index['fund_type'] = '指数型'
                data['fund_rank_index'] = df_index
                print(f"  ✓ 获取指数型基金近1年TOP50: {len(df_index)} 只")
        except Exception as e:
            print(f"  ✗ 获取指数型基金失败: {e}")
            data['fund_rank_index'] = pd.DataFrame()

        return data

    def apply_filters(self, raw_data: Dict[str, Any]) -> List[Dict]:
        """Apply long-term filtering rules - 严格筛选."""
        candidates = []

        for key in ['fund_rank_stock', 'fund_rank_mixed', 'fund_rank_index']:
            df = raw_data.get(key, pd.DataFrame())
            if df.empty:
                continue

            for _, row in df.iterrows():
                try:
                    code = str(row.get('基金代码', '')).strip()
                    name = str(row.get('基金简称', ''))

                    # 基本排除
                    if 'QDII' in name:
                        continue
                    if 'C' in code[-1:]:  # 排除C类份额
                        continue

                    # 获取业绩指标
                    return_1y = self._safe_float(row.get('近1年'))
                    return_2y = self._safe_float(row.get('近2年'))
                    return_3y = self._safe_float(row.get('近3年'))
                    return_6m = self._safe_float(row.get('近6月'))
                    return_3m = self._safe_float(row.get('近3月'))
                    return_1m = self._safe_float(row.get('近1月'))

                    # ===== 严格筛选条件 =====

                    # 1. 必须有1年业绩数据
                    if return_1y is None:
                        continue

                    # 2. 近1年 > 5%（有明显正收益）
                    if return_1y <= 5:
                        continue

                    # 3. 近6月 > 0%（中期趋势向好）
                    if return_6m is not None and return_6m <= 0:
                        continue

                    # 4. 如果有3年数据，3年收益 > 15%
                    if return_3y is not None and return_3y <= 15:
                        continue

                    has_long_history = return_3y is not None

                    candidate = {
                        'code': code,
                        'name': name,
                        'type': 'open_fund',
                        'fund_type': row.get('fund_type', ''),
                        'return_1w': self._safe_float(row.get('近1周')),
                        'return_1m': return_1m,
                        'return_3m': return_3m,
                        'return_6m': return_6m,
                        'return_1y': return_1y,
                        'return_2y': return_2y,
                        'return_3y': return_3y,
                        'nav': self._safe_float(row.get('单位净值')),
                        'nav_date': str(row.get('日期', '')),
                        'has_long_history': has_long_history,
                    }

                    candidates.append(candidate)

                except Exception as e:
                    continue

        print(f"  ✓ 严格筛选后: {len(candidates)} 只基金")
        return candidates

    def calculate_scores(self, candidates: List[Dict]) -> List[Dict]:
        """Calculate composite score for long-term funds."""
        if not candidates:
            return []

        # Get metrics for normalization
        returns_1y = [c.get('return_1y', 0) for c in candidates if c.get('return_1y') is not None]
        returns_3y = [c.get('return_3y', 0) for c in candidates if c.get('return_3y') is not None]

        max_1y = max(returns_1y) if returns_1y else 1
        min_1y = min(returns_1y) if returns_1y else 0
        max_3y = max(returns_3y) if returns_3y else 1
        min_3y = min(returns_3y) if returns_3y else 0

        for c in candidates:
            score = 0

            # 1. Long-term performance (35%)
            r1y = c.get('return_1y', 0) or 0
            r3y = c.get('return_3y')

            # 1-year return score (20%)
            if max_1y != min_1y:
                score_1y = (r1y - min_1y) / (max_1y - min_1y) * 20
            else:
                score_1y = 10
            score += score_1y

            # 3-year return score (15%) - bonus for long history
            if r3y is not None and max_3y != min_3y:
                score_3y = (r3y - min_3y) / (max_3y - min_3y) * 15
            elif r3y is not None:
                score_3y = 7.5
            else:
                score_3y = 5  # Penalty for no long history
            score += score_3y

            # 2. Risk-adjusted return placeholder (25%)
            # Estimate using performance consistency
            r1m = c.get('return_1m', 0) or 0
            r3m = c.get('return_3m', 0) or 0
            r6m = c.get('return_6m', 0) or 0

            # Check consistency (all positive periods = good)
            positive_periods = sum([
                1 if r1m > 0 else 0,
                1 if r3m > 0 else 0,
                1 if r6m > 0 else 0,
                1 if r1y > 0 else 0
            ])
            score += positive_periods * 6.25  # Max 25 if all positive

            # 3. Fund manager placeholder (25%)
            score += 12.5

            # 4. Holdings quality placeholder (15%)
            score += 7.5

            c['score'] = round(score, 2)

        return candidates

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        if value is None or value == '' or value == '--':
            return None
        try:
            if isinstance(value, str):
                value = value.replace(',', '').replace('%', '')
            return float(value)
        except (ValueError, TypeError):
            return None
