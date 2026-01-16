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
    2. Collect additional data for candidates
    3. Generate AI-powered recommendations using LLM
    4. Format and return results
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
    ) -> Dict[str, Any]:
        """
        Generate investment recommendations.

        Args:
            mode: "short", "long", or "all"
            stock_limit: Maximum stocks to screen
            fund_limit: Maximum funds to screen
            use_llm: Whether to use LLM for final analysis

        Returns:
            Dict containing recommendations and metadata
        """
        print(f"\n{'='*60}")
        print(f"🚀 开始生成AI投资推荐 | 模式: {mode}")
        print(f"{'='*60}\n")

        start_time = datetime.now()
        results = {
            "mode": mode,
            "generated_at": start_time.isoformat(),
            "short_term": None,
            "long_term": None,
            "metadata": {
                "screening_time": 0,
                "llm_time": 0,
                "total_time": 0,
            }
        }

        # Step 1: Screen candidates
        print("📊 Step 1: 筛选候选标的...")
        screening_start = datetime.now()

        if mode in ["short", "all"]:
            print("\n--- 短期股票筛选 ---")
            short_stocks = self.short_term_stock_screener.screen(limit=stock_limit)
            print(f"\n--- 短期基金筛选 ---")
            short_funds = self.short_term_fund_screener.screen(limit=fund_limit)
        else:
            short_stocks, short_funds = [], []

        if mode in ["long", "all"]:
            print("\n--- 长期股票筛选 ---")
            long_stocks = self.long_term_stock_screener.screen(limit=stock_limit)
            print(f"\n--- 长期基金筛选 ---")
            long_funds = self.long_term_fund_screener.screen(limit=fund_limit)
        else:
            long_stocks, long_funds = [], []

        screening_time = (datetime.now() - screening_start).total_seconds()
        results["metadata"]["screening_time"] = screening_time
        print(f"\n✓ 筛选完成，耗时: {screening_time:.1f}秒")

        # Step 2: Generate LLM recommendations
        if use_llm and self.llm:
            print("\n🤖 Step 2: AI分析与推荐生成...")
            llm_start = datetime.now()

            if mode in ["short", "all"]:
                results["short_term"] = self._generate_short_term_recommendations(
                    short_stocks, short_funds
                )

            if mode in ["long", "all"]:
                results["long_term"] = self._generate_long_term_recommendations(
                    long_stocks, long_funds
                )

            llm_time = (datetime.now() - llm_start).total_seconds()
            results["metadata"]["llm_time"] = llm_time
            print(f"\n✓ AI分析完成，耗时: {llm_time:.1f}秒")
        else:
            # Return raw screening results without LLM
            print("\n📋 Step 2: 跳过AI分析，返回筛选结果...")
            if mode in ["short", "all"]:
                results["short_term"] = {
                    "stocks": short_stocks[:15],
                    "funds": short_funds[:10],
                    "market_view": "需配置LLM获取AI分析",
                }

            if mode in ["long", "all"]:
                results["long_term"] = {
                    "stocks": long_stocks[:15],
                    "funds": long_funds[:10],
                    "macro_view": "需配置LLM获取AI分析",
                }

        total_time = (datetime.now() - start_time).total_seconds()
        results["metadata"]["total_time"] = total_time

        print(f"\n{'='*60}")
        print(f"✅ 推荐生成完成！总耗时: {total_time:.1f}秒")
        print(f"{'='*60}\n")

        return results

    def _generate_short_term_recommendations(
        self,
        stocks: List[Dict],
        funds: List[Dict],
    ) -> Dict[str, Any]:
        """Generate short-term recommendations using LLM."""
        from src.llm.recommendation_prompts import SHORT_TERM_RECOMMENDATION_PROMPT

        # Prepare candidate data for prompt - 只取TOP20股票和TOP15基金
        stock_data = self._format_stock_candidates(stocks[:20])
        fund_data = self._format_fund_candidates(funds[:15])

        # Get market context
        market_context = self._get_market_context()
        hot_sectors = self._get_hot_sectors()

        # Build prompt
        prompt = SHORT_TERM_RECOMMENDATION_PROMPT.format(
            stock_count=min(len(stocks), 20),
            stock_candidates_data=stock_data,
            fund_count=min(len(funds), 15),
            fund_candidates_data=fund_data,
            market_context=market_context,
            hot_sectors=hot_sectors,
            report_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

        # Call LLM
        try:
            response = self.llm.generate_content(prompt)
            result = self._parse_llm_response(response)

            if result:
                return result
        except Exception as e:
            print(f"  ✗ LLM分析失败: {e}")

        # Fallback to simple selection
        return {
            "short_term_stocks": self._simple_select_stocks(stocks, limit=8),
            "short_term_funds": self._simple_select_funds(funds, limit=5),
            "market_view": "AI分析暂时不可用，返回筛选结果",
            "sector_preference": [],
            "risk_warning": "请结合自身判断进行投资决策",
        }

    def _generate_long_term_recommendations(
        self,
        stocks: List[Dict],
        funds: List[Dict],
    ) -> Dict[str, Any]:
        """Generate long-term recommendations using LLM."""
        from src.llm.recommendation_prompts import LONG_TERM_RECOMMENDATION_PROMPT

        # Prepare candidate data - 只取TOP20股票和TOP15基金
        stock_data = self._format_stock_candidates(stocks[:20], long_term=True)
        fund_data = self._format_fund_candidates(funds[:15], long_term=True)

        # Get macro context
        macro_context = self._get_macro_context()
        industry_outlook = self._get_industry_outlook()

        # Build prompt
        prompt = LONG_TERM_RECOMMENDATION_PROMPT.format(
            stock_count=min(len(stocks), 20),
            stock_candidates_data=stock_data,
            fund_count=min(len(funds), 15),
            fund_candidates_data=fund_data,
            macro_context=macro_context,
            industry_outlook=industry_outlook,
            report_date=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

        # Call LLM
        try:
            response = self.llm.generate_content(prompt)
            result = self._parse_llm_response(response)

            if result:
                return result
        except Exception as e:
            print(f"  ✗ LLM分析失败: {e}")

        # Fallback
        return {
            "long_term_stocks": self._simple_select_stocks(stocks, limit=8),
            "long_term_funds": self._simple_select_funds(funds, limit=5),
            "macro_view": "AI分析暂时不可用，返回筛选结果",
            "sector_preference": [],
            "risk_warning": "请结合自身判断进行投资决策",
        }

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

    def _simple_select_stocks(self, stocks: List[Dict], limit: int = 8) -> List[Dict]:
        """Simple selection of top stocks by score."""
        selected = []
        for s in stocks[:limit]:
            selected.append({
                "code": s.get("code"),
                "name": s.get("name"),
                "current_price": s.get("price"),
                "recommendation_score": s.get("score", 50),
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
                "fund_type": f.get("fund_type", ""),
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
