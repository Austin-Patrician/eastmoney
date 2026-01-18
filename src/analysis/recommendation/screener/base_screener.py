"""
Base Screener - Abstract base class for all screeners.
"""
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from datetime import datetime


class BaseScreener(ABC):
    """
    Abstract base class for screening stocks or funds.

    Subclasses implement specific screening logic for:
    - Short-term stocks (7+ days)
    - Long-term stocks (3+ months)
    - Short-term funds (7+ days)
    - Long-term funds (3+ months)
    """

    def __init__(self, cache_manager=None):
        """
        Initialize screener.

        Args:
            cache_manager: Optional cache manager for caching API results
        """
        self.cache = cache_manager
        self.screening_date = datetime.now().strftime("%Y-%m-%d")
        self.user_preferences: Optional[Dict[str, Any]] = None

    @property
    @abstractmethod
    def screener_type(self) -> str:
        """Return screener type identifier (e.g., 'short_term_stock')."""
        pass

    @property
    @abstractmethod
    def default_limit(self) -> int:
        """Default number of candidates to return."""
        pass

    @abstractmethod
    def collect_raw_data(self) -> Dict[str, Any]:
        """
        Collect raw data from data sources.

        Returns:
            Dict containing raw data needed for screening
        """
        pass

    @abstractmethod
    def apply_filters(self, raw_data: Dict[str, Any]) -> List[Dict]:
        """
        Apply filtering rules to raw data.

        Args:
            raw_data: Raw data from collect_raw_data()

        Returns:
            List of candidates that pass all filters
        """
        pass

    @abstractmethod
    def calculate_scores(self, candidates: List[Dict]) -> List[Dict]:
        """
        Calculate composite scores for candidates.

        Args:
            candidates: List of filtered candidates

        Returns:
            List of candidates with 'score' field added
        """
        pass

    def screen(self, limit: int = None, user_preferences: Optional[Dict[str, Any]] = None) -> List[Dict]:
        """
        Execute the full screening pipeline.

        Args:
            limit: Maximum number of candidates to return
            user_preferences: Optional user preferences for early filtering

        Returns:
            Sorted list of scored candidates
        """
        limit = limit or self.default_limit
        self.user_preferences = user_preferences

        # Step 1: Collect raw data
        raw_data = self.collect_raw_data()

        # Step 2: Apply filters (including user preferences if provided)
        candidates = self.apply_filters(raw_data)

        # Step 3: Calculate scores
        scored = self.calculate_scores(candidates)

        # Step 4: Sort by score (descending) and limit
        sorted_candidates = sorted(scored, key=lambda x: x.get('score', 0), reverse=True)

        return sorted_candidates[:limit]

    def _apply_user_preference_filters(self, stock: Dict) -> bool:
        """
        Apply user preference filters to a stock. Returns True if stock passes all filters.

        This is a helper method that can be called in apply_filters() to do early filtering.
        """
        if not self.user_preferences:
            return True

        prefs = self.user_preferences

        # 1. Market cap filter
        market_cap = stock.get('market_cap')
        min_cap = prefs.get('min_market_cap')
        max_cap = prefs.get('max_market_cap')

        if min_cap and market_cap and market_cap < min_cap:
            return False
        if max_cap and market_cap and market_cap > max_cap:
            return False

        # 2. PE filter
        pe = stock.get('pe')
        min_pe = prefs.get('min_pe')
        max_pe = prefs.get('max_pe')

        if pe is not None and pe > 0:
            if min_pe and pe < min_pe:
                return False
            if max_pe and pe > max_pe:
                return False

        # 3. Require profitable (PE > 0)
        if prefs.get('require_profitable', True):
            if pe is not None and pe <= 0:
                return False

        # 4. Avoid ST stocks
        if prefs.get('avoid_st_stocks', True):
            name = stock.get('name', '')
            if 'ST' in name or '*ST' in name:
                return False

        # 5. Sector filter
        stock_sector = stock.get('sector', '')
        preferred_sectors = prefs.get('preferred_sectors', [])
        excluded_sectors = prefs.get('excluded_sectors', [])

        # Skip if in excluded sectors
        if excluded_sectors and stock_sector:
            if any(exc in stock_sector for exc in excluded_sectors):
                return False

        # Skip if preferred_sectors specified but stock not in any of them
        if preferred_sectors and stock_sector:
            if not any(pref in stock_sector for pref in preferred_sectors):
                return False

        # 6. Liquidity filter
        min_liquidity = prefs.get('min_liquidity')
        turnover = stock.get('turnover')
        if min_liquidity and turnover and turnover < min_liquidity:
            return False

        return True

    def _boost_preferred_sector_score(self, stock: Dict) -> float:
        """Get score boost multiplier for preferred sectors."""
        if not self.user_preferences:
            return 1.0

        preferred_sectors = self.user_preferences.get('preferred_sectors', [])
        stock_sector = stock.get('sector', '')

        if preferred_sectors and stock_sector:
            if any(pref in stock_sector for pref in preferred_sectors):
                return 1.2  # 20% boost

        return 1.0

    def _cache_key(self, suffix: str) -> str:
        """Generate cache key with screener type and date."""
        return f"screener:{self.screener_type}:{self.screening_date}:{suffix}"

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get value from cache if available."""
        if self.cache:
            return self.cache.get(self._cache_key(key))
        return None

    def _set_cached(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set value in cache if available."""
        if self.cache:
            self.cache.set(self._cache_key(key), value, ttl)
