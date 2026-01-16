"""
Stock Screeners - Short-term and Long-term stock screening implementations.
"""
import akshare as ak
import pandas as pd
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from .base_screener import BaseScreener


class ShortTermStockScreener(BaseScreener):
    """
    Short-term stock screener (7+ days holding period).

    Focuses on:
    - Capital flow (资金流向) - 30% weight
    - Technical momentum (技术动量) - 25% weight
    - Market heat (市场热度) - 20% weight
    - Northbound flow (北向资金) - 15% weight
    - Sector momentum (板块联动) - 10% weight
    """

    @property
    def screener_type(self) -> str:
        return "short_term_stock"

    @property
    def default_limit(self) -> int:
        return 30  # 只返回前30只

    def collect_raw_data(self) -> Dict[str, Any]:
        """Collect data from AkShare APIs."""
        data = {}

        # 1. 获取资金流向排行TOP100（核心数据，优先获取）
        try:
            df = ak.stock_individual_fund_flow_rank(indicator="今日")
            if df is not None and not df.empty:
                # 只取净流入前200名
                df = df.head(200)
                data['fund_flow'] = df
                print(f"  ✓ 获取资金流向TOP200: {len(df)} 条")
        except Exception as e:
            print(f"  ✗ 获取资金流向失败: {e}")
            data['fund_flow'] = pd.DataFrame()

        # 2. 获取人气榜TOP100
        try:
            df = ak.stock_hot_rank_em()
            if df is not None and not df.empty:
                data['hot_rank'] = df.head(100)
                print(f"  ✓ 获取人气榜TOP100: {len(data['hot_rank'])} 只")
        except Exception as e:
            print(f"  ✗ 获取人气榜失败: {e}")
            data['hot_rank'] = pd.DataFrame()

        # 3. 获取行业板块涨幅榜TOP20
        try:
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                data['sector_perf'] = df.head(20)
                print(f"  ✓ 获取热门行业TOP20: {len(data['sector_perf'])} 个")
        except Exception as e:
            print(f"  ✗ 获取行业板块失败: {e}")
            data['sector_perf'] = pd.DataFrame()

        # 4. 获取资金流入股票的实时行情（只查询资金流入的股票）
        if not data.get('fund_flow', pd.DataFrame()).empty:
            try:
                codes = data['fund_flow']['代码'].tolist()
                spot_map = self._get_stock_spot_batch(codes)
                data['stock_spot'] = spot_map
                print(f"  ✓ 获取候选股票行情: {len(spot_map)} 只")
            except Exception as e:
                print(f"  ✗ 获取股票行情失败: {e}")
                data['stock_spot'] = {}

        return data

    def _get_stock_spot_batch(self, codes: List[str]) -> Dict[str, Dict]:
        """批量获取股票行情，使用全市场数据过滤"""
        try:
            df = ak.stock_zh_a_spot_em()
            if df is None or df.empty:
                return {}

            # 过滤出需要的股票
            code_set = set(str(c).zfill(6) for c in codes)
            filtered = df[df['代码'].isin(code_set)]
            return filtered.set_index('代码').to_dict('index')
        except Exception as e:
            print(f"  批量获取行情失败: {e}")
            return {}

    def apply_filters(self, raw_data: Dict[str, Any]) -> List[Dict]:
        """Apply short-term filtering rules - 更严格的筛选."""
        candidates = []

        fund_flow = raw_data.get('fund_flow', pd.DataFrame())
        hot_rank = raw_data.get('hot_rank', pd.DataFrame())
        stock_spot = raw_data.get('stock_spot', {})

        if fund_flow.empty:
            print("  ✗ 无资金流向数据，无法筛选")
            return []

        # 构建热门股票集合
        hot_codes = set()
        if not hot_rank.empty and '代码' in hot_rank.columns:
            hot_codes = set(str(c).zfill(6) for c in hot_rank['代码'].tolist())

        # 基于资金流向筛选
        for _, row in fund_flow.iterrows():
            try:
                code = str(row.get('代码', '')).zfill(6)
                name = str(row.get('名称', ''))

                # 基本排除条件
                if 'ST' in name or '*ST' in name:
                    continue
                if name.startswith('N') or name.startswith('C'):
                    continue
                if code.startswith('900') or code.startswith('200'):
                    continue

                # 获取实时行情数据
                spot = stock_spot.get(code, {})

                price = self._safe_float(spot.get('最新价'))
                change_pct = self._safe_float(spot.get('涨跌幅'))
                market_cap = self._safe_float(spot.get('总市值'))
                pe = self._safe_float(spot.get('市盈率-动态'))
                volume_ratio = self._safe_float(spot.get('量比'))
                turnover = self._safe_float(spot.get('成交额'))

                # 资金流向数据
                main_net_inflow = self._safe_float(row.get('主力净流入-净额'))
                main_net_pct = self._safe_float(row.get('主力净流入-净占比'))

                # ===== 严格筛选条件 =====

                # 1. 市值 > 100亿（流动性好）
                if market_cap and market_cap < 1e10:
                    continue

                # 2. 价格 > 5元（避免低价股）
                if price and price < 5:
                    continue

                # 3. 成交额 > 1亿（活跃度）
                if not turnover or turnover < 1e8:
                    continue

                # 4. 涨跌幅在合理区间（-5% ~ 8%，避免追涨停）
                if change_pct is not None and (change_pct >= 8 or change_pct <= -5):
                    continue

                # 5. PE > 0 且 < 100（盈利且估值不太高）
                if pe is not None and (pe <= 0 or pe > 100):
                    continue

                # 6. 主力净流入 > 0（必须有资金流入）
                if main_net_inflow is None or main_net_inflow <= 0:
                    continue

                # 7. 量比 > 1（放量）
                if volume_ratio and volume_ratio < 1:
                    continue

                candidate = {
                    'code': code,
                    'name': name,
                    'price': price,
                    'change_pct': change_pct,
                    'turnover': turnover,
                    'market_cap': market_cap,
                    'pe': pe,
                    'volume_ratio': volume_ratio,
                    'main_net_inflow': main_net_inflow,
                    'main_net_inflow_pct': main_net_pct,
                    'is_hot': code in hot_codes,
                }

                candidates.append(candidate)

            except Exception as e:
                continue

        print(f"  ✓ 严格筛选后: {len(candidates)} 只股票")
        return candidates

    def calculate_scores(self, candidates: List[Dict]) -> List[Dict]:
        """Calculate composite score for each candidate."""
        if not candidates:
            return []

        # 获取最大值用于归一化
        max_inflow = max((c.get('main_net_inflow', 0) or 0 for c in candidates), default=1)

        for c in candidates:
            score = 0

            # 1. 资金流向得分 (35%)
            inflow = c.get('main_net_inflow', 0) or 0
            if max_inflow > 0:
                score += (inflow / max_inflow) * 35

            # 2. 量比得分 (20%)
            vr = c.get('volume_ratio', 1) or 1
            if 1.5 <= vr <= 3:
                score += 20
            elif 1 <= vr < 1.5:
                score += 15
            elif vr > 3:
                score += 10
            else:
                score += 5

            # 3. 涨幅得分 (15%)
            change = c.get('change_pct', 0) or 0
            if 2 <= change <= 5:
                score += 15
            elif 0 < change < 2:
                score += 12
            elif 5 < change < 8:
                score += 8
            else:
                score += 5

            # 4. 热度加分 (15%)
            if c.get('is_hot'):
                score += 15
            else:
                score += 5

            # 5. 估值得分 (15%)
            pe = c.get('pe', 50)
            if pe and 0 < pe <= 30:
                score += 15
            elif pe and 30 < pe <= 50:
                score += 10
            else:
                score += 5

            c['score'] = round(score, 2)

        # 按分数排序
        candidates.sort(key=lambda x: x.get('score', 0), reverse=True)
        return candidates

    def _safe_float(self, value) -> Optional[float]:
        """Safely convert value to float."""
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = value.replace(',', '').replace('%', '')
            return float(value)
        except (ValueError, TypeError):
            return None


class LongTermStockScreener(BaseScreener):
    """
    Long-term stock screener (3+ months holding period).

    基于基本面筛选优质股票。
    """

    @property
    def screener_type(self) -> str:
        return "long_term_stock"

    @property
    def default_limit(self) -> int:
        return 30

    def collect_raw_data(self) -> Dict[str, Any]:
        """Collect data - 只获取必要数据."""
        data = {}

        # 获取全市场数据一次
        try:
            df = ak.stock_zh_a_spot_em()
            if df is not None and not df.empty:
                data['stock_spot'] = df
                print(f"  ✓ 获取A股行情: {len(df)} 只")
        except Exception as e:
            print(f"  ✗ 获取A股行情失败: {e}")
            data['stock_spot'] = pd.DataFrame()

        return data

    def apply_filters(self, raw_data: Dict[str, Any]) -> List[Dict]:
        """Apply long-term filtering rules - 严格基本面筛选."""
        candidates = []

        stock_spot = raw_data.get('stock_spot', pd.DataFrame())

        if stock_spot.empty:
            return []

        for _, row in stock_spot.iterrows():
            try:
                code = str(row.get('代码', '')).zfill(6)
                name = str(row.get('名称', ''))

                # 基本排除
                if 'ST' in name or '*ST' in name:
                    continue
                if name.startswith('N') or name.startswith('C'):
                    continue
                if code.startswith('900') or code.startswith('200'):
                    continue

                # 获取指标
                price = self._safe_float(row.get('最新价'))
                market_cap = self._safe_float(row.get('总市值'))
                pe = self._safe_float(row.get('市盈率-动态'))
                pb = self._safe_float(row.get('市净率'))
                turnover = self._safe_float(row.get('成交额'))
                change_60d = self._safe_float(row.get('60日涨跌幅'))

                # ===== 严格长期筛选条件 =====

                # 1. 市值 > 200亿（大中盘，稳定性好）
                if market_cap and market_cap < 2e10:
                    continue

                # 2. PE > 0 且 < 40（盈利且估值合理）
                if pe is None or pe <= 0 or pe > 40:
                    continue

                # 3. PB > 0 且 < 8（资产质量）
                if pb is None or pb <= 0 or pb > 8:
                    continue

                # 4. 成交额 > 5000万（流动性）
                if not turnover or turnover < 5e7:
                    continue

                # 5. 60日涨跌幅 > -20%（排除大幅下跌的问题股）
                if change_60d is not None and change_60d < -20:
                    continue

                candidate = {
                    'code': code,
                    'name': name,
                    'price': price,
                    'market_cap': market_cap,
                    'pe': pe,
                    'pb': pb,
                    'turnover': turnover,
                    'change_pct': self._safe_float(row.get('涨跌幅')),
                    'change_60d': change_60d,
                }

                candidates.append(candidate)

            except Exception as e:
                continue

        print(f"  ✓ 严格筛选后: {len(candidates)} 只股票")
        return candidates

    def calculate_scores(self, candidates: List[Dict]) -> List[Dict]:
        """Calculate composite score for long-term investment."""
        if not candidates:
            return []

        for c in candidates:
            score = 0

            # 1. 估值得分 (40%)
            pe = c.get('pe', 50)
            pb = c.get('pb', 5)

            if pe <= 15:
                score += 20
            elif pe <= 25:
                score += 15
            elif pe <= 35:
                score += 10
            else:
                score += 5

            if pb <= 2:
                score += 20
            elif pb <= 4:
                score += 15
            elif pb <= 6:
                score += 10
            else:
                score += 5

            # 2. 市值得分 (30%) - 大市值更稳定
            cap = c.get('market_cap', 0)
            if cap >= 5e11:  # 5000亿+
                score += 30
            elif cap >= 2e11:  # 2000亿+
                score += 25
            elif cap >= 1e11:  # 1000亿+
                score += 20
            elif cap >= 5e10:  # 500亿+
                score += 15
            else:
                score += 10

            # 3. 趋势得分 (30%)
            change_60d = c.get('change_60d')
            if change_60d is not None:
                if change_60d > 10:
                    score += 30
                elif change_60d > 0:
                    score += 25
                elif change_60d > -10:
                    score += 15
                else:
                    score += 5
            else:
                score += 15

            c['score'] = round(score, 2)

        candidates.sort(key=lambda x: x.get('score', 0), reverse=True)
        return candidates

    def _safe_float(self, value) -> Optional[float]:
        if value is None:
            return None
        try:
            if isinstance(value, str):
                value = value.replace(',', '').replace('%', '')
            return float(value)
        except (ValueError, TypeError):
            return None
