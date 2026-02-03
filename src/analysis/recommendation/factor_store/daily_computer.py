"""
Daily Factor Computer - Batch computation of stock and fund factors.

Designed for 2H4G server:
- Batch processing (100 stocks/batch)
- Limited concurrency (4 threads max)
- Scheduled to run at 6:00 AM daily
- Tier-based rate limiting for TuShare API (auto-configured from TUSHARE_POINTS env var)
"""
import time
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

from src.data_sources.tushare_client import (
    get_latest_trade_date,
    format_date_yyyymmdd,
)
from src.storage.db import (
    get_db_connection,
    upsert_stock_factors,
    upsert_fund_factors,
    delete_old_stock_factors,
    delete_old_fund_factors,
)
from .cache import factor_cache
from .rate_limiter import tushare_rate_limiter

# Print rate limiter configuration on module load
_rate_limiter_stats = tushare_rate_limiter.get_stats()
print(f"[RateLimiter] Initialized for {_rate_limiter_stats['tier_name']} "
      f"({_rate_limiter_stats['points']} points): "
      f"{_rate_limiter_stats['max_calls']} calls/minute "
      f"(raw limit: {_rate_limiter_stats['raw_limit']}, "
      f"safety margin: {_rate_limiter_stats['safety_margin']:.0%})")


class DailyFactorComputer:
    """
    Computes factors for all A-shares and funds daily.

    Optimized for limited resources:
    - Batch processing to reduce memory
    - Tier-based global rate limiter for TuShare API (auto-configured)
    - Progress tracking for long-running jobs
    """

    # Configuration
    BATCH_SIZE = 100
    MAX_WORKERS = 4  # Parallel workers per batch

    def __init__(self):
        self._running = False
        self._progress = {
            'total': 0,
            'completed': 0,
            'failed': 0,
            'current_batch': 0,
            'status': 'idle'
        }
        self._lock = threading.Lock()

    @property
    def progress(self) -> Dict:
        """Get current computation progress."""
        with self._lock:
            return dict(self._progress)

    @property
    def is_running(self) -> bool:
        """Check if computation is in progress."""
        return self._running

    def _update_progress(self, **kwargs) -> None:
        """Update progress state."""
        with self._lock:
            self._progress.update(kwargs)

    def _get_all_stock_codes(self) -> List[str]:
        """Get all active A-share stock codes from database."""
        conn = get_db_connection()
        results = conn.execute(
            "SELECT ts_code FROM stock_basic WHERE list_status = 'L'"
        ).fetchall()
        conn.close()
        return [r[0] for r in results]

    def _get_all_fund_codes(self, universe: str = "tracked") -> List[str]:
        """
        Get fund codes from database.

        Args:
            universe: Which universe to use
                - "tracked": User's tracked funds (funds.is_active=1)
                - "market": All market funds from fund_basic table (全市场)
                - "market_otc": OTC funds only (场外基金, market='O')
                - "market_etf": Exchange-traded funds only (场内基金, market='E')

        Returns:
            List of fund codes
        """
        conn = get_db_connection()

        if universe == "tracked":
            # User's tracked funds (original behavior)
            results = conn.execute(
                "SELECT DISTINCT code FROM funds WHERE is_active = 1"
            ).fetchall()
        elif universe == "market":
            # All market funds from fund_basic
            results = conn.execute(
                "SELECT DISTINCT code FROM fund_basic WHERE status = 'L'"
            ).fetchall()
        elif universe == "market_otc":
            # OTC funds only (场外)
            results = conn.execute(
                "SELECT DISTINCT code FROM fund_basic WHERE status = 'L' AND market = 'O'"
            ).fetchall()
        elif universe == "market_etf":
            # Exchange-traded funds only (场内)
            results = conn.execute(
                "SELECT DISTINCT code FROM fund_basic WHERE status = 'L' AND market = 'E'"
            ).fetchall()
        else:
            conn.close()
            raise ValueError(f"Invalid universe: {universe}. Must be 'tracked', 'market', 'market_otc', or 'market_etf'")

        conn.close()
        return [r[0] for r in results]

    def _compute_stock_factors_single(
        self,
        ts_code: str,
        trade_date: str
    ) -> Tuple[str, Optional[Dict]]:
        """
        Compute all factors for a single stock.

        Args:
            ts_code: TuShare format stock code
            trade_date: Trade date in YYYYMMDD format

        Returns:
            Tuple of (code, factors_dict or None if failed)
        """
        # Rate limiting is now handled inside tushare_call_with_retry

        # Import here to avoid circular imports
        try:
            from src.analysis.recommendation.stock_engine.factors.technical import TechnicalFactors
            from src.analysis.recommendation.stock_engine.factors.fundamental import FundamentalFactors
            from src.analysis.recommendation.stock_engine.factors.sentiment import SentimentFactors
            from src.analysis.recommendation.stock_engine.strategies.short_term import ShortTermStrategy
            from src.analysis.recommendation.stock_engine.strategies.long_term import LongTermStrategy
        except ImportError as e:
            print(f"Factor modules not yet implemented: {e}")
            return ts_code, None

        try:
            # Compute individual factor groups
            technical = TechnicalFactors.compute(ts_code, trade_date)
            fundamental = FundamentalFactors.compute(ts_code, trade_date)
            sentiment = SentimentFactors.compute(ts_code, trade_date)

            # Merge all factors
            factors = {
                **technical,
                **fundamental,
                **sentiment,
            }

            # Compute composite scores
            factors['short_term_score'] = ShortTermStrategy.compute_score(factors)
            factors['long_term_score'] = LongTermStrategy.compute_score(factors)

            return ts_code, factors

        except Exception as e:
            print(f"Error computing factors for {ts_code}: {e}")
            return ts_code, None

    def _compute_fund_factors_single(
        self,
        fund_code: str,
        trade_date: str
    ) -> Tuple[str, Optional[Dict]]:
        """
        Compute all factors for a single fund.

        Args:
            fund_code: Fund code
            trade_date: Trade date

        Returns:
            Tuple of (code, factors_dict or None if failed)
        """
        # Rate limiting is now handled inside tushare_call_with_retry

        try:
            from src.analysis.recommendation.fund_engine.factors.performance import PerformanceFactors
            from src.analysis.recommendation.fund_engine.factors.risk import RiskFactors
            from src.analysis.recommendation.fund_engine.factors.manager import ManagerFactors
            from src.analysis.recommendation.fund_engine.strategies.momentum import MomentumStrategy
            from src.analysis.recommendation.fund_engine.strategies.alpha import AlphaStrategy
        except ImportError as e:
            print(f"Fund factor modules not yet implemented: {e}")
            return fund_code, None

        try:
            performance = PerformanceFactors.compute(fund_code, trade_date)
            risk = RiskFactors.compute(fund_code, trade_date)
            manager = ManagerFactors.compute(fund_code, trade_date)

            factors = {
                **performance,
                **risk,
                **manager,
            }

            factors['short_term_score'] = MomentumStrategy.compute_score(factors)
            factors['long_term_score'] = AlphaStrategy.compute_score(factors)

            return fund_code, factors

        except Exception as e:
            print(f"Error computing factors for fund {fund_code}: {e}")
            return fund_code, None

    def _process_batch(
        self,
        codes: List[str],
        trade_date: str,
        asset_type: str = 'stock'
    ) -> Tuple[int, int]:
        """
        Process a batch of codes.

        Args:
            codes: List of stock/fund codes
            trade_date: Trade date
            asset_type: 'stock' or 'fund'

        Returns:
            Tuple of (success_count, failure_count)
        """
        success = 0
        failure = 0

        compute_func = (
            self._compute_stock_factors_single if asset_type == 'stock'
            else self._compute_fund_factors_single
        )
        persist_func = upsert_stock_factors if asset_type == 'stock' else upsert_fund_factors

        # Convert trade_date format for DB storage
        trade_date_db = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"

        # Print rate limiter stats before batch
        stats = tushare_rate_limiter.get_stats()
        print(f"[Batch Start] Tier: {stats['tier_name']}, "
              f"Usage: {stats['current_calls']}/{stats['max_calls']} calls "
              f"({stats['utilization']:.1f}%)")

        # Collect factors first, then persist in batches to reduce lock contention
        computed_factors = []

        with ThreadPoolExecutor(max_workers=self.MAX_WORKERS) as executor:
            futures = {
                executor.submit(compute_func, code, trade_date): code
                for code in codes
            }

            for future in as_completed(futures):
                code = futures[future]
                try:
                    _, factors = future.result()

                    if factors:
                        factors['code'] = code.split('.')[0] if '.' in code else code
                        factors['trade_date'] = trade_date_db
                        computed_factors.append(factors)
                        success += 1
                    else:
                        failure += 1

                except Exception as e:
                    print(f"Batch processing error for {code}: {e}")
                    failure += 1

        # Persist all factors after computation (serialized to avoid lock contention)
        for factors in computed_factors:
            try:
                persist_func(factors)
            except Exception as e:
                print(f"Failed to persist factors for {factors.get('code')}: {e}")

        # Print rate limiter stats after batch
        stats = tushare_rate_limiter.get_stats()
        print(f"[Batch End] Usage: {stats['current_calls']}/{stats['max_calls']} calls "
              f"({stats['utilization']:.1f}%)")

        return success, failure

    def compute_all_stock_factors(self, trade_date: str = None) -> Dict:
        """
        Compute factors for all A-shares.

        Args:
            trade_date: Trade date in YYYYMMDD format (default: latest trade date)

        Returns:
            Summary dict with success/failure counts
        """
        if self._running:
            return {'error': 'Computation already in progress'}

        self._running = True

        if not trade_date:
            trade_date = get_latest_trade_date()
            if not trade_date:
                trade_date = format_date_yyyymmdd()

        print(f"Starting stock factor computation for {trade_date}...")

        try:
            # Get all stock codes
            all_codes = self._get_all_stock_codes()

            if not all_codes:
                # If no stocks in DB, try to sync from TuShare
                from src.data_sources.tushare_client import sync_stock_basic
                sync_stock_basic()
                all_codes = self._get_all_stock_codes()

            total = len(all_codes)
            self._update_progress(
                total=total,
                completed=0,
                failed=0,
                current_batch=0,
                status='running'
            )

            print(f"Processing {total} stocks in batches of {self.BATCH_SIZE}...")

            total_success = 0
            total_failure = 0

            # Process in batches
            for i in range(0, total, self.BATCH_SIZE):
                batch = all_codes[i:i + self.BATCH_SIZE]
                batch_num = i // self.BATCH_SIZE + 1

                self._update_progress(current_batch=batch_num)
                print(f"Processing batch {batch_num} ({len(batch)} stocks)...")

                success, failure = self._process_batch(batch, trade_date, 'stock')
                total_success += success
                total_failure += failure

                self._update_progress(
                    completed=self._progress['completed'] + success + failure,
                    failed=self._progress['failed'] + failure
                )

            # Clear cache for the date to force refresh
            factor_cache.clear_for_date(trade_date)

            self._update_progress(status='completed')

            result = {
                'trade_date': trade_date,
                'total': total,
                'success': total_success,
                'failure': total_failure,
                'duration_seconds': 0  # TODO: track actual duration
            }

            print(f"Stock factor computation completed: {result}")
            return result

        except Exception as e:
            self._update_progress(status=f'error: {str(e)}')
            print(f"Stock factor computation failed: {e}")
            return {'error': str(e)}

        finally:
            self._running = False

    def compute_all_fund_factors(self, trade_date: str = None, universe: str = "market_otc") -> Dict:
        """
        Compute factors for funds.

        Args:
            trade_date: Trade date in YYYYMMDD format
            universe: Which fund universe to compute
                - "tracked": User's tracked funds only (default)
                - "market": All market funds (requires fund_basic table synced)
                - "market_otc": OTC funds only (场外基金)
                - "market_etf": Exchange-traded funds only (场内基金)

        Returns:
            Summary dict with success/failure counts
        """
        if self._running:
            return {'error': 'Computation already in progress'}

        self._running = True

        if not trade_date:
            trade_date = get_latest_trade_date()
            if not trade_date:
                trade_date = format_date_yyyymmdd()

        print(f"Starting fund factor computation for {trade_date} (universe={universe})...")

        try:
            all_codes = self._get_all_fund_codes(universe=universe)
            total = len(all_codes)

            if total == 0:
                if universe != "tracked":
                    # Try to sync fund_basic if market universe is empty
                    print("No funds in fund_basic, attempting to sync...")
                    from src.data_sources.tushare_client import sync_fund_basic
                    sync_fund_basic()
                    all_codes = self._get_all_fund_codes(universe=universe)
                    total = len(all_codes)

            if total == 0:
                print(f"No funds to process (universe={universe})")
                return {'trade_date': trade_date, 'universe': universe, 'total': 0, 'success': 0, 'failure': 0}

            self._update_progress(
                total=total,
                completed=0,
                failed=0,
                current_batch=0,
                status='running'
            )

            print(f"Processing {total} funds...")

            total_success = 0
            total_failure = 0

            for i in range(0, total, self.BATCH_SIZE):
                batch = all_codes[i:i + self.BATCH_SIZE]
                batch_num = i // self.BATCH_SIZE + 1

                self._update_progress(current_batch=batch_num)

                success, failure = self._process_batch(batch, trade_date, 'fund')
                total_success += success
                total_failure += failure

                self._update_progress(
                    completed=self._progress['completed'] + success + failure,
                    failed=self._progress['failed'] + failure
                )

            factor_cache.clear_for_date(trade_date)

            self._update_progress(status='completed')

            result = {
                'trade_date': trade_date,
                'universe': universe,
                'total': total,
                'success': total_success,
                'failure': total_failure,
            }

            print(f"Fund factor computation completed: {result}")
            return result

        except Exception as e:
            self._update_progress(status=f'error: {str(e)}')
            print(f"Fund factor computation failed: {e}")
            return {'error': str(e)}

        finally:
            self._running = False

    def cleanup_old_data(self, days_to_keep: int = 30) -> Dict:
        """
        Clean up old factor data to save disk space.

        Args:
            days_to_keep: Number of days of data to retain

        Returns:
            Cleanup summary
        """
        stock_deleted = delete_old_stock_factors(days_to_keep)
        fund_deleted = delete_old_fund_factors(days_to_keep)

        return {
            'stock_factors_deleted': stock_deleted,
            'fund_factors_deleted': fund_deleted
        }


# Global instance
daily_computer = DailyFactorComputer()


def run_daily_computation():
    """
    Entry point for scheduled daily factor computation.

    This function is designed to be called by APScheduler at 6:00 AM.
    """
    print(f"[{datetime.now()}] Starting daily factor computation...")

    # Get latest trade date
    trade_date = get_latest_trade_date()

    if not trade_date:
        print("Could not determine latest trade date, skipping computation")
        return

    # Compute stock factors first
    stock_result = daily_computer.compute_all_stock_factors(trade_date)
    print(f"Stock factors: {stock_result}")

    # Then compute fund factors
    fund_result = daily_computer.compute_all_fund_factors(trade_date)
    print(f"Fund factors: {fund_result}")

    # Cleanup old data
    cleanup_result = daily_computer.cleanup_old_data(days_to_keep=30)
    print(f"Cleanup: {cleanup_result}")

    print(f"[{datetime.now()}] Daily factor computation completed")
