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

    def screen(self, limit: int = None) -> List[Dict]:
        """
        Execute the full screening pipeline.

        Args:
            limit: Maximum number of candidates to return

        Returns:
            Sorted list of scored candidates
        """
        limit = limit or self.default_limit

        # Step 1: Collect raw data
        raw_data = self.collect_raw_data()

        # Step 2: Apply filters
        candidates = self.apply_filters(raw_data)

        # Step 3: Calculate scores
        scored = self.calculate_scores(candidates)

        # Step 4: Sort by score (descending) and limit
        sorted_candidates = sorted(scored, key=lambda x: x.get('score', 0), reverse=True)

        return sorted_candidates[:limit]

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
