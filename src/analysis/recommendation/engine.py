"""
Recommendation Engine - Main orchestrator for AI investment recommendations.
"""
import json
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

from .screener import (
    ShortTermStockScreener,
    LongTermStockScreener,
    ShortTermFundScreener,
    LongTermFundScreener,
)


class RecommendationEngine:
    """
    AI Investment Recommendation Engine.

    Orchestrates the full recommendation pipeline:
    1. Screen candidates using multiple screeners
    2. Apply user preferences to filter candidates
    3. Collect additional data for candidates
    4. Generate AI-powered recommendations using LLM
    5. Format and return results
    """

    def __init__(self, llm_client=None, web_search=None, cache_manager=None):
        """
        Initialize the recommendation engine.

        Args:
            llm_client: LLM client for AI analysis
            web_search: Web search client for news/research
            cache_manager: Cache manager for caching results
        """
        self.llm = llm_client
        self.web_search = web_search
        self.cache = cache_manager

        # Initialize screeners
        self.short_term_stock_screener = ShortTermStockScreener(cache_manager)
        self.long_term_stock_screener = LongTermStockScreener(cache_manager)
        self.short_term_fund_screener = ShortTermFundScreener(cache_manager)
        self.long_term_fund_screener = LongTermFundScreener(cache_manager)

    def generate_recommendations(
        self,
        mode: str = "all",
        stock_limit: int = 30,
        fund_limit: int = 20,
        use_llm: bool = True,
        user_preferences: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate investment recommendations.

        Args:
            mode: "short", "long", or "all"
            stock_limit: Maximum stocks to screen
            fund_limit: Maximum funds to screen
            use_llm: Whether to use LLM for final analysis
            user_preferences: User's personalized preferences (optional)

        Returns:
            Dict containing recommendations and metadata
        """
        is_personalized = user_preferences is not None
        print(f"\n{'='*60}")
        print(f"🚀 开始生成AI投资推荐 | 模式: {mode} | 个性化: {'是' if is_personalized else '否'}")
        print(f"{'='*60}\n")

        if is_personalized:
            self._log_preferences_summary(user_preferences)

        start_time = datetime.now()
        results = {
            "mode": mode,
            "generated_at": start_time.isoformat(),
            "personalized": is_personalized,
            "short_term": None,
            "long_term": None,
            "metadata": {
                "screening_time": 0,
                "llm_time": 0,
                "total_time": 0,
                "personalized": is_personalized,
            }
        }

        # Step 1: Screen candidates (with user preferences for early filtering)
        print("📊 Step 1: 筛选候选标的...")
        screening_start = datetime.now()

        if mode in ["short", "all"]:
            print("\n--- 短期股票筛选 ---")
            short_stocks = self.short_term_stock_screener.screen(
                limit=stock_limit,
                user_preferences=user_preferences
            )
            print(f"\n--- 短期基金筛选 ---")
            short_funds = self.short_term_fund_screener.screen(
                limit=fund_limit,
                user_preferences=user_preferences
            )
        else:
            short_stocks, short_funds = [], []

        if mode in ["long", "all"]:
            print("\n--- 长期股票筛选 ---")
            long_stocks = self.long_term_stock_screener.screen(
                limit=stock_limit,
                user_preferences=user_preferences
            )
            print(f"\n--- 长期基金筛选 ---")
            long_funds = self.long_term_fund_screener.screen(
                limit=fund_limit,
                user_preferences=user_preferences
            )
        else:
            long_stocks, long_funds = [], []

        screening_time = (datetime.now() - screening_start).total_seconds()
        results["metadata"]["screening_time"] = screening_time
        print(f"\n✓ 筛选完成，耗时: {screening_time:.1f}秒")

        # Note: User preference filtering is now done EARLY in the screener itself
        # The following Step 1.5 is kept for backward compatibility but may be redundant
        if user_preferences:
            print("\n🎯 用户偏好已在筛选阶段应用")
            print(f"  短期: {len(short_stocks)} 只股票, {len(short_funds)} 只基金")
            print(f"  长期: {len(long_stocks)} 只股票, {len(long_funds)} 只基金")

        # Get recommendation counts from preferences
        stock_rec_count = user_preferences.get('stock_recommendation_count', 8) if user_preferences else 8
        fund_rec_count = user_preferences.get('fund_recommendation_count', 5) if user_preferences else 5

        # Step 2: Generate LLM recommendations
        if use_llm and self.llm:
            print("\n🤖 Step 2: AI分析与推荐生成...")
            llm_start = datetime.now()

            if mode in ["short", "all"]:
                results["short_term"] = self._generate_short_term_recommendations(
                    short_stocks, short_funds, user_preferences, stock_rec_count, fund_rec_count
                )

            if mode in ["long", "all"]:
                results["long_term"] = self._generate_long_term_recommendations(
                    long_stocks, long_funds, user_preferences, stock_rec_count, fund_rec_count
                )

            llm_time = (datetime.now() - llm_start).total_seconds()
            results["metadata"]["llm_time"] = llm_time
            print(f"\n✓ AI分析完成，耗时: {llm_time:.1f}秒")
        else:
            # Return raw screening results without LLM
            print("\n📋 Step 2: 跳过AI分析，返回筛选结果...")
            if mode in ["short", "all"]:
                results["short_term"] = {
                    "stocks": short_stocks[:stock_rec_count],
                    "funds": short_funds[:fund_rec_count],
                    "market_view": "需配置LLM获取AI分析",
                }

            if mode in ["long", "all"]:
                results["long_term"] = {
                    "stocks": long_stocks[:stock_rec_count],
                    "funds": long_funds[:fund_rec_count],
                    "macro_view": "需配置LLM获取AI分析",
                }

        total_time = (datetime.now() - start_time).total_seconds()
        results["metadata"]["total_time"] = total_time

        print(f"\n{'='*60}")
        print(f"✅ 推荐生成完成！总耗时: {total_time:.1f}秒")
        if is_personalized:
            print(f"📌 已根据用户偏好过滤（风险等级: {user_preferences.get('risk_level', 'moderate')}）")
        print(f"{'='*60}\n")

        return results

    def _log_preferences_summary(self, prefs: Dict[str, Any]) -> None:
        """Log a summary of user preferences."""
        print(f"  📋 用户偏好摘要:")
        print(f"     - 风险等级: {prefs.get('risk_level', 'moderate')}")
        print(f"     - 投资期限: {prefs.get('investment_horizon', 'medium_term')}")
        print(f"     - 投资风格: {prefs.get('investment_style', 'blend')}")
        if prefs.get('min_market_cap'):
            print(f"     - 最小市值: {prefs.get('min_market_cap') / 1e8:.0f}亿")
        if prefs.get('max_pe'):
            print(f"     - 最大PE: {prefs.get('max_pe')}")
        if prefs.get('preferred_sectors'):
            print(f"     - 偏好行业: {', '.join(prefs.get('preferred_sectors', []))}")
        if prefs.get('excluded_sectors'):
            print(f"     - 排除行业: {', '.join(prefs.get('excluded_sectors', []))}")
        if prefs.get('preferred_fund_types'):
            print(f"     - 偏好基金类型: {', '.join(prefs.get('preferred_fund_types', []))}")
        if prefs.get('excluded_fund_types'):
            print(f"     - 排除基金类型: {', '.join(prefs.get('excluded_fund_types', []))}")
        if prefs.get('max_drawdown_tolerance'):
            print(f"     - 最大回撤容忍: {prefs.get('max_drawdown_tolerance') * 100:.0f}%")
        if prefs.get('stop_loss_percentage'):
            print(f"     - 止损比例: {prefs.get('stop_loss_percentage') * 100:.0f}%")
        if prefs.get('stock_recommendation_count'):
            print(f"     - 股票推荐数量: {prefs.get('stock_recommendation_count')}")
        if prefs.get('fund_recommendation_count'):
            print(f"     - 基金推荐数量: {prefs.get('fund_recommendation_count')}")

    def _apply_stock_preferences(
        self,
        stocks: List[Dict],
        prefs: Dict[str, Any]
    ) -> List[Dict]:
        """
        Apply user preferences to filter and prioritize stocks.

        Args:
            stocks: List of screened stock candidates
            prefs: User preferences dictionary

        Returns:
            Filtered list of stocks matching user preferences
        """
        filtered = []

        for stock in stocks:
            # 1. Market cap filter
            market_cap = stock.get('market_cap')
            min_cap = prefs.get('min_market_cap')
            max_cap = prefs.get('max_market_cap')

            if min_cap and market_cap and market_cap < min_cap:
                continue
            if max_cap and market_cap and market_cap > max_cap:
                continue

            # 2. PE filter
            pe = stock.get('pe')
            min_pe = prefs.get('min_pe')
            max_pe = prefs.get('max_pe')

            if pe is not None and pe > 0:  # Only apply PE filter for positive PE
                if min_pe and pe < min_pe:
                    continue
                if max_pe and pe > max_pe:
                    continue

            # 3. Require profitable (PE > 0)
            if prefs.get('require_profitable', True):
                if pe is not None and pe <= 0:
                    continue

            # 4. Avoid ST stocks
            if prefs.get('avoid_st_stocks', True):
                name = stock.get('name', '')
                if 'ST' in name or '*ST' in name:
                    continue

            # 5. Sector preference (boost score if in preferred sectors)
            stock_sector = stock.get('sector', '')
            preferred_sectors = prefs.get('preferred_sectors', [])
            excluded_sectors = prefs.get('excluded_sectors', [])

            # Skip if in excluded sectors
            if excluded_sectors and stock_sector:
                if any(exc in stock_sector for exc in excluded_sectors):
                    continue

            # Boost score if in preferred sectors
            if preferred_sectors and stock_sector:
                if any(pref in stock_sector for pref in preferred_sectors):
                    stock = stock.copy()
                    stock['score'] = stock.get('score', 50) * 1.2  # 20% boost

            filtered.append(stock)

        # Sort by score descending
        filtered.sort(key=lambda x: x.get('score', 0), reverse=True)

        return filtered

    def _apply_fund_preferences(
        self,
        funds: List[Dict],
        prefs: Dict[str, Any]
    ) -> List[Dict]:
        """
        Apply user preferences to filter and prioritize funds.

        Args:
            funds: List of screened fund candidates
            prefs: User preferences dictionary

        Returns:
            Filtered list of funds matching user preferences
        """
        filtered = []

        preferred_types = prefs.get('preferred_fund_types', [])
        excluded_types = prefs.get('excluded_fund_types', [])
        min_scale = prefs.get('min_fund_scale')

        for fund in funds:
            fund_type = fund.get('fund_type', '')

            # 1. Fund type filter - EXCLUDE if not in preferred types (when preferred_types is set)
            if preferred_types:
                # Check if fund_type matches any preferred type
                type_matched = any(pref in fund_type for pref in preferred_types)
                if not type_matched:
                    continue  # Skip funds not in preferred types

            # 2. Fund type filter - EXCLUDE if in excluded types
            if excluded_types:
                if any(exc in fund_type for exc in excluded_types):
                    continue

            # 3. Fund scale filter (if available)
            fund_scale = fund.get('scale') or fund.get('fund_scale')
            if min_scale and fund_scale and fund_scale < min_scale:
                continue

            # Boost score if in preferred types (already filtered, so all remaining are preferred or no filter)
            if preferred_types:
                if any(pref in fund_type for pref in preferred_types):
                    fund = fund.copy()
                    fund['score'] = fund.get('score', 50) * 1.1  # 10% boost for exact match

            filtered.append(fund)

        # Sort by score descending
        filtered.sort(key=lambda x: x.get('score', 0), reverse=True)

        return filtered

    def _generate_short_term_recommendations(
        self,
        stocks: List[Dict],
        funds: List[Dict],
        user_preferences: Optional[Dict[str, Any]] = None,
        stock_limit: int = 8,
        fund_limit: int = 5,
    ) -> Dict[str, Any]:
        """Generate short-term recommendations using LLM."""
        from src.llm.recommendation_prompts import SHORT_TERM_RECOMMENDATION_PROMPT

        # Prepare candidate data for prompt - 只取TOP20股票和TOP15基金
        stock_data = self._format_stock_candidates(stocks[:20])
        fund_data = self._format_fund_candidates(funds[:15])

        # Get market context
        market_context = self._get_market_context()
        hot_sectors = self._get_hot_sectors()

        # Add personalization context if available
        personalization_context = ""
        if user_preferences:
            personalization_context = self._format_personalization_context(user_preferences)

        # Build prompt
        prompt = SHORT_TERM_RECOMMENDATION_PROMPT.format(
            stock_count=min(len(stocks), 20),
            stock_candidates_data=stock_data,
            fund_count=min(len(funds), 15),
            fund_candidates_data=fund_data,
            market_context=market_context,
            hot_sectors=hot_sectors,
            report_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            personalization_context=personalization_context,
            stock_recommendation_count=stock_limit,
            fund_recommendation_count=fund_limit,
        )

        # Call LLM
        try:
            response = self.llm.generate_content(prompt)
            result = self._parse_llm_response(response)

            if result:
                # Enrich LLM recommendations with original candidate data
                result = self._enrich_recommendations(result, stocks, funds, is_short_term=True)
                return result
        except Exception as e:
            print(f"  ✗ LLM分析失败: {e}")

        # Fallback to simple selection
        return {
            "short_term_stocks": self._simple_select_stocks(stocks, limit=stock_limit),
            "short_term_funds": self._simple_select_funds(funds, limit=fund_limit),
            "market_view": "AI分析暂时不可用，返回筛选结果",
            "sector_preference": [],
            "risk_warning": "请结合自身判断进行投资决策",
        }

    def _generate_long_term_recommendations(
        self,
        stocks: List[Dict],
        funds: List[Dict],
        user_preferences: Optional[Dict[str, Any]] = None,
        stock_limit: int = 8,
        fund_limit: int = 5,
    ) -> Dict[str, Any]:
        """Generate long-term recommendations using LLM."""
        from src.llm.recommendation_prompts import LONG_TERM_RECOMMENDATION_PROMPT

        # Prepare candidate data - 只取TOP20股票和TOP15基金
        stock_data = self._format_stock_candidates(stocks[:20], long_term=True)
        fund_data = self._format_fund_candidates(funds[:15], long_term=True)

        # Get macro context
        macro_context = self._get_macro_context()
        industry_outlook = self._get_industry_outlook()

        # Add personalization context if available
        personalization_context = ""
        if user_preferences:
            personalization_context = self._format_personalization_context(user_preferences)

        # Build prompt
        prompt = LONG_TERM_RECOMMENDATION_PROMPT.format(
            stock_count=min(len(stocks), 20),
            stock_candidates_data=stock_data,
            fund_count=min(len(funds), 15),
            fund_candidates_data=fund_data,
            macro_context=macro_context,
            industry_outlook=industry_outlook,
            report_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
            personalization_context=personalization_context,
            stock_recommendation_count=stock_limit,
            fund_recommendation_count=fund_limit,
        )

        # Call LLM
        try:
            response = self.llm.generate_content(prompt)
            result = self._parse_llm_response(response)

            if result:
                # Enrich LLM recommendations with original candidate data
                result = self._enrich_recommendations(result, stocks, funds, is_short_term=False)
                return result
        except Exception as e:
            print(f"  ✗ LLM分析失败: {e}")

        # Fallback
        return {
            "long_term_stocks": self._simple_select_stocks(stocks, limit=stock_limit),
            "long_term_funds": self._simple_select_funds(funds, limit=fund_limit),
            "macro_view": "AI分析暂时不可用，返回筛选结果",
            "sector_preference": [],
            "risk_warning": "请结合自身判断进行投资决策",
        }

    def _format_personalization_context(self, prefs: Dict[str, Any]) -> str:
        """Format user preferences as context for LLM prompt."""
        lines = []
        lines.append("\n【用户个性化偏好】")

        risk_labels = {
            'conservative': '保守型（追求本金安全，低风险）',
            'moderate': '稳健型（平衡风险与收益）',
            'aggressive': '积进型（追求较高收益，接受中等风险）',
            'speculative': '投机型（追求高收益，接受高风险）'
        }
        risk_level = prefs.get('risk_level', 'moderate')
        lines.append(f"- 风险偏好: {risk_labels.get(risk_level, risk_level)}")

        horizon_labels = {
            'short_term': '短期（7-30天）',
            'medium_term': '中期（1-6月）',
            'long_term': '长期（6月以上）'
        }
        horizon = prefs.get('investment_horizon', 'medium_term')
        lines.append(f"- 投资期限: {horizon_labels.get(horizon, horizon)}")

        style_labels = {
            'value': '价值投资',
            'growth': '成长投资',
            'blend': '均衡',
            'momentum': '动量投资',
            'dividend': '股息投资'
        }
        style = prefs.get('investment_style', 'blend')
        lines.append(f"- 投资风格: {style_labels.get(style, style)}")

        if prefs.get('preferred_sectors'):
            lines.append(f"- 偏好行业: {', '.join(prefs.get('preferred_sectors'))}")

        if prefs.get('excluded_sectors'):
            lines.append(f"- 排除行业: {', '.join(prefs.get('excluded_sectors'))}")

        if prefs.get('max_drawdown_tolerance'):
            lines.append(f"- 最大回撤容忍: {prefs.get('max_drawdown_tolerance') * 100:.0f}%")

        if prefs.get('stop_loss_percentage'):
            lines.append(f"- 止损比例: {prefs.get('stop_loss_percentage') * 100:.0f}%")

        lines.append("\n请根据以上用户偏好，优先推荐符合用户风险承受能力和投资风格的标的。")

        return "\n".join(lines)

    def _format_stock_candidates(self, stocks: List[Dict], long_term: bool = False) -> str:
        """Format stock candidates for LLM prompt."""
        lines = []
        for i, s in enumerate(stocks, 1):
            if long_term:
                line = (
                    f"{i}. {s.get('code')} {s.get('name')} | "
                    f"价格:{s.get('price', 'N/A')} | "
                    f"PE:{s.get('pe', 'N/A')} | "
                    f"PB:{s.get('pb', 'N/A')} | "
                    f"市值:{self._format_market_cap(s.get('market_cap'))} | "
                    f"评分:{s.get('score', 0)}"
                )
            else:
                line = (
                    f"{i}. {s.get('code')} {s.get('name')} | "
                    f"价格:{s.get('price', 'N/A')} | "
                    f"涨跌:{s.get('change_pct', 0):.2f}% | "
                    f"主力净流入:{self._format_amount(s.get('main_net_inflow'))} | "
                    f"量比:{s.get('volume_ratio', 'N/A')} | "
                    f"评分:{s.get('score', 0)}"
                )
            lines.append(line)
        return "\n".join(lines)

    def _format_fund_candidates(self, funds: List[Dict], long_term: bool = False) -> str:
        """Format fund candidates for LLM prompt."""
        lines = []
        for i, f in enumerate(funds, 1):
            if long_term:
                line = (
                    f"{i}. {f.get('code')} {f.get('name')} | "
                    f"类型:{f.get('fund_type', 'N/A')} | "
                    f"近1年:{f.get('return_1y', 'N/A')}% | "
                    f"近3年:{f.get('return_3y', 'N/A')}% | "
                    f"评分:{f.get('score', 0)}"
                )
            else:
                line = (
                    f"{i}. {f.get('code')} {f.get('name')} | "
                    f"类型:{f.get('fund_type', 'N/A')} | "
                    f"近1周:{f.get('return_1w', 'N/A')}% | "
                    f"近1月:{f.get('return_1m', 'N/A')}% | "
                    f"评分:{f.get('score', 0)}"
                )
            lines.append(line)
        return "\n".join(lines)

    def _format_market_cap(self, cap) -> str:
        """Format market cap to readable string."""
        if cap is None:
            return "N/A"
        try:
            cap = float(cap)
            if cap >= 1e12:
                return f"{cap/1e12:.1f}万亿"
            elif cap >= 1e8:
                return f"{cap/1e8:.1f}亿"
            else:
                return f"{cap/1e4:.1f}万"
        except:
            return "N/A"

    def _format_amount(self, amount) -> str:
        """Format amount to readable string."""
        if amount is None:
            return "N/A"
        try:
            amount = float(amount)
            if abs(amount) >= 1e8:
                return f"{amount/1e8:.2f}亿"
            elif abs(amount) >= 1e4:
                return f"{amount/1e4:.1f}万"
            else:
                return f"{amount:.0f}"
        except:
            return "N/A"

    def _get_market_context(self) -> str:
        """Get current market context for short-term analysis."""
        try:
            from src.data_sources.akshare_api import get_northbound_flow, get_market_indices

            indices = get_market_indices()
            northbound = get_northbound_flow()

            context = []
            for name, data in indices.items():
                change = data.get('涨跌幅', 'N/A')
                context.append(f"{name}: {change}%")

            nb_flow = northbound.get('最新净流入', 'N/A')
            context.append(f"北向资金: {nb_flow}")

            return " | ".join(context)
        except Exception as e:
            return "市场数据获取失败"

    def _get_hot_sectors(self) -> str:
        """Get hot sectors information."""
        try:
            import akshare as ak
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                top5 = df.head(5)
                sectors = []
                for _, row in top5.iterrows():
                    name = row.get('板块名称', '')
                    change = row.get('涨跌幅', 0)
                    sectors.append(f"{name}({change:.1f}%)")
                return ", ".join(sectors)
        except:
            pass
        return "热点板块数据获取失败"

    def _get_macro_context(self) -> str:
        """Get macro economic context for long-term analysis."""
        try:
            from src.data_sources.akshare_api import get_global_macro_summary

            macro = get_global_macro_summary()
            context = []

            us_market = macro.get('美股市场', {})
            for name, data in us_market.items():
                if isinstance(data, dict):
                    change = data.get('涨跌幅', 'N/A')
                    context.append(f"{name}: {change}")

            return " | ".join(context[:3]) if context else "宏观数据获取中..."
        except:
            return "宏观数据获取失败"

    def _get_industry_outlook(self) -> str:
        """Get industry outlook information."""
        try:
            import akshare as ak
            df = ak.stock_board_industry_name_em()
            if df is not None and not df.empty:
                # Get top and bottom sectors
                top3 = df.head(3)
                bottom3 = df.tail(3)

                outlook = ["领涨行业:"]
                for _, row in top3.iterrows():
                    outlook.append(f"  {row.get('板块名称', '')}({row.get('涨跌幅', 0):.1f}%)")

                outlook.append("领跌行业:")
                for _, row in bottom3.iterrows():
                    outlook.append(f"  {row.get('板块名称', '')}({row.get('涨跌幅', 0):.1f}%)")

                return "\n".join(outlook)
        except:
            pass
        return "行业数据获取失败"

    def _parse_llm_response(self, response: str) -> Optional[Dict]:
        """Parse LLM response to extract JSON."""
        if not response:
            return None

        try:
            # Try to find JSON in response
            response = response.strip()

            # Remove markdown code blocks if present
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]

            # Find JSON object
            start = response.find("{")
            end = response.rfind("}") + 1

            if start >= 0 and end > start:
                json_str = response[start:end]
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"  ✗ JSON解析失败: {e}")
        except Exception as e:
            print(f"  ✗ 响应处理失败: {e}")

        return None

    def _enrich_recommendations(
        self,
        result: Dict[str, Any],
        stocks: List[Dict],
        funds: List[Dict],
        is_short_term: bool = True
    ) -> Dict[str, Any]:
        """
        Enrich LLM recommendations with original candidate data.

        LLM may not include all fields (change_pct, pe, market_cap, etc.),
        so we merge them from the original candidate data.
        """
        # Create lookup maps for quick access
        stock_map = {s.get('code'): s for s in stocks}
        fund_map = {f.get('code'): f for f in funds}

        # Enrich stocks
        stock_key = "short_term_stocks" if is_short_term else "long_term_stocks"
        if stock_key in result:
            for rec_stock in result[stock_key]:
                code = rec_stock.get('code')
                if code and code in stock_map:
                    original = stock_map[code]
                    # Merge missing fields from original data
                    if 'change_pct' not in rec_stock or rec_stock['change_pct'] is None:
                        rec_stock['change_pct'] = original.get('change_pct')
                    if 'pe' not in rec_stock or rec_stock['pe'] is None:
                        rec_stock['pe'] = original.get('pe')
                    if 'pb' not in rec_stock or rec_stock['pb'] is None:
                        rec_stock['pb'] = original.get('pb')
                    if 'market_cap' not in rec_stock or rec_stock['market_cap'] is None:
                        rec_stock['market_cap'] = original.get('market_cap')
                    if 'price' not in rec_stock or rec_stock['price'] is None:
                        rec_stock['price'] = original.get('price')
                    if 'score' not in rec_stock or rec_stock['score'] is None:
                        rec_stock['score'] = original.get('score')

                    # Short-term specific fields
                    if is_short_term:
                        if 'main_net_inflow' not in rec_stock or rec_stock['main_net_inflow'] is None:
                            rec_stock['main_net_inflow'] = original.get('main_net_inflow')
                        if 'volume_ratio' not in rec_stock or rec_stock['volume_ratio'] is None:
                            rec_stock['volume_ratio'] = original.get('volume_ratio')

        # Enrich funds
        fund_key = "short_term_funds" if is_short_term else "long_term_funds"
        if fund_key in result:
            for rec_fund in result[fund_key]:
                code = rec_fund.get('code')
                if code and code in fund_map:
                    original = fund_map[code]
                    # Merge missing fields from original data
                    if 'fund_type' not in rec_fund or not rec_fund['fund_type']:
                        rec_fund['fund_type'] = original.get('fund_type', '')
                    if 'return_1w' not in rec_fund or rec_fund['return_1w'] is None:
                        rec_fund['return_1w'] = original.get('return_1w')
                    if 'return_1m' not in rec_fund or rec_fund['return_1m'] is None:
                        rec_fund['return_1m'] = original.get('return_1m')
                    if 'return_1y' not in rec_fund or rec_fund['return_1y'] is None:
                        rec_fund['return_1y'] = original.get('return_1y')
                    if 'return_3y' not in rec_fund or rec_fund['return_3y'] is None:
                        rec_fund['return_3y'] = original.get('return_3y')
                    if 'score' not in rec_fund or rec_fund['score'] is None:
                        rec_fund['score'] = original.get('score')

        return result

    def _simple_select_stocks(self, stocks: List[Dict], limit: int = 8) -> List[Dict]:
        """Simple selection of top stocks by score."""
        selected = []
        for s in stocks[:limit]:
            selected.append({
                "code": s.get("code"),
                "name": s.get("name"),
                "current_price": s.get("price"),
                "price": s.get("price"),  # For compatibility
                "change_pct": s.get("change_pct"),
                "pe": s.get("pe"),
                "market_cap": s.get("market_cap"),
                "main_net_inflow": s.get("main_net_inflow"),
                "volume_ratio": s.get("volume_ratio"),
                "recommendation_score": s.get("score", 50),
                "score": s.get("score", 50),  # For compatibility
                "investment_logic": f"综合评分{s.get('score', 50)}分，量化筛选入选",
                "confidence": "中",
            })
        return selected

    def _simple_select_funds(self, funds: List[Dict], limit: int = 5) -> List[Dict]:
        """Simple selection of top funds by score."""
        selected = []
        for f in funds[:limit]:
            selected.append({
                "code": f.get("code"),
                "name": f.get("name"),
                "current_nav": f.get("nav") or f.get("price"),
                "recommendation_score": f.get("score", 50),
                "score": f.get("score", 50),  # For compatibility
                "fund_type": f.get("fund_type", ""),
                "return_1w": f.get("return_1w"),
                "return_1m": f.get("return_1m"),
                "return_1y": f.get("return_1y"),
                "return_3y": f.get("return_3y"),
                "investment_logic": f"综合评分{f.get('score', 50)}分，量化筛选入选",
                "confidence": "中",
            })
        return selected

    def get_cached_recommendations(self, user_id: int = None, mode: str = "all") -> Optional[Dict]:
        """Get cached recommendations if available."""
        if not self.cache:
            return None

        cache_key = f"recommendations:{user_id or 'global'}:{mode}"
        return self.cache.get(cache_key)

    def cache_recommendations(self, results: Dict, user_id: int = None, ttl: int = 14400):
        """Cache recommendations (default 4 hours)."""
        if not self.cache:
            return

        mode = results.get("mode", "all")
        cache_key = f"recommendations:{user_id or 'global'}:{mode}"
        self.cache.set(cache_key, results, ttl)
