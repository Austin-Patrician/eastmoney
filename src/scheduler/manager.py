import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import logging
import asyncio
from datetime import datetime, date
from typing import Dict, Optional, Set
from src.storage.db import (
    get_active_funds, get_fund_by_code, get_active_stocks, get_stock_by_code,
    get_all_portfolios, get_portfolio_positions, save_portfolio_snapshot, get_latest_snapshot
)
from src.analysis.pre_market import PreMarketAnalyst
from src.analysis.post_market import PostMarketAnalyst
from src.analysis.dashboard import DashboardService
from src.report_gen import save_report, save_stock_report

logger = logging.getLogger(__name__)


class TradingCalendar:
    """Trading calendar utility using akshare data"""
    _instance = None
    _trading_dates: Set[str] = set()
    _last_refresh: Optional[date] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(TradingCalendar, cls).__new__(cls)
        return cls._instance

    def refresh_calendar(self) -> bool:
        """Refresh trading calendar from akshare, cache for the day"""
        today = date.today()
        if self._last_refresh == today and self._trading_dates:
            return True

        try:
            import akshare as ak
            df = ak.tool_trade_date_hist_sina()
            # Column is 'trade_date' with format like '2024-01-02'
            self._trading_dates = set(df['trade_date'].astype(str).tolist())
            self._last_refresh = today
            logger.info(f"Trading calendar refreshed, {len(self._trading_dates)} trading dates loaded")
            return True
        except Exception as e:
            logger.error(f"Failed to refresh trading calendar: {e}")
            return False

    def is_trading_day(self, check_date: Optional[date] = None) -> bool:
        """Check if a given date is a trading day"""
        if check_date is None:
            check_date = date.today()

        # Refresh calendar if needed
        if not self._trading_dates or self._last_refresh != date.today():
            if not self.refresh_calendar():
                # Fallback: assume weekdays are trading days if API fails
                logger.warning("Using fallback: treating weekdays as trading days")
                return check_date.weekday() < 5

        date_str = check_date.strftime('%Y-%m-%d')
        return date_str in self._trading_dates


# Global trading calendar instance
trading_calendar = TradingCalendar()

class SchedulerManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SchedulerManager, cls).__new__(cls)
            cls._instance.scheduler = BackgroundScheduler()
            cls._instance.scheduler.start()
        return cls._instance

    def start(self):
        """Load jobs from DB and start"""
        print("Starting Scheduler Manager...")
        self.refresh_all_jobs()
        self.add_dashboard_refresh_job()
        self.add_daily_snapshot_job()
        self.add_factor_computation_job()

    def refresh_all_jobs(self):
        """Clear all and reload from DB (All users)"""
        self.scheduler.remove_all_jobs()
        # Fetch ALL active funds from ALL users
        funds = get_active_funds(user_id=None)
        for fund in funds:
            self.add_fund_jobs(fund)
        # Fetch ALL active stocks from ALL users
        stocks = get_active_stocks(user_id=None)
        for stock in stocks:
            self.add_stock_jobs(stock)
        # Re-add dashboard job since we removed all
        self.add_dashboard_refresh_job()
        # Re-add daily snapshot job
        self.add_daily_snapshot_job()
        # Re-add factor computation job
        self.add_factor_computation_job()

    def add_dashboard_refresh_job(self):
        """Schedule dashboard cache refresh every 5 minutes"""
        job_id = "dashboard_refresh"
        if not self.scheduler.get_job(job_id):
            self.scheduler.add_job(
                self.refresh_dashboard_cache,
                trigger=IntervalTrigger(minutes=5),
                id=job_id,
                replace_existing=True,
                max_instances=3,
                coalesce=True
            )
            print("Scheduled dashboard cache refresh every 5 minutes")

    def refresh_dashboard_cache(self):
        """Worker to refresh global dashboard cache"""
        try:
            # Report dir is not critical for global market data, just pass current dir
            service = DashboardService(os.getcwd())
            service.get_full_dashboard(force_refresh=True)
            print("Dashboard cache refreshed.")
        except Exception as e:
            print(f"Error refreshing dashboard cache: {e}")

    def add_daily_snapshot_job(self):
        """Schedule daily portfolio snapshot creation at 23:00 (after market close)"""
        job_id = "daily_portfolio_snapshots"
        if not self.scheduler.get_job(job_id):
            self.scheduler.add_job(
                self.create_all_portfolio_snapshots,
                trigger=CronTrigger(hour=23, minute=0),
                id=job_id,
                replace_existing=True,
                max_instances=1,
                coalesce=True
            )
            print("Scheduled daily portfolio snapshots at 23:00")

    def add_factor_computation_job(self):
        """Schedule daily factor computation at 6:00 AM (before market open)"""
        job_id = "daily_factor_computation"
        if not self.scheduler.get_job(job_id):
            self.scheduler.add_job(
                self.run_daily_factor_computation,
                trigger=CronTrigger(hour=6, minute=0),
                id=job_id,
                replace_existing=True,
                max_instances=1,
                coalesce=True
            )
            print("Scheduled daily factor computation at 06:00")

    def run_daily_factor_computation(self):
        """Worker to run daily factor computation for recommendation system v2"""
        # Check if today is a trading day
        if not trading_calendar.is_trading_day():
            print("Skipping factor computation - not a trading day")
            return

        try:
            from src.analysis.recommendation.factor_store.daily_computer import run_daily_computation
            print("Starting daily factor computation...")
            run_daily_computation()
            print("Daily factor computation completed.")
        except ImportError as e:
            print(f"Factor computation module not available: {e}")
        except Exception as e:
            print(f"Error running daily factor computation: {e}")

    def create_all_portfolio_snapshots(self):
        """Create snapshots for all portfolios (called by scheduler)"""
        # Check if today is a trading day
        if not trading_calendar.is_trading_day():
            print("Skipping portfolio snapshots - not a trading day")
            return

        print("Creating daily portfolio snapshots...")
        portfolios = get_all_portfolios()
        snapshot_date = date.today().strftime('%Y-%m-%d')
        created_count = 0
        error_count = 0
        skipped_count = 0

        for portfolio in portfolios:
            try:
                portfolio_id = portfolio['id']
                user_id = portfolio['user_id']

                positions = get_portfolio_positions(portfolio_id, user_id)
                if not positions:
                    continue

                # Calculate portfolio value using current prices
                # CRITICAL: Do NOT use avg_cost as fallback - this would corrupt P&L data
                total_value = 0
                total_cost = 0
                missing_assets = []  # Track assets where price fetch failed
                is_complete = True   # Flag to mark if all prices were fetched successfully

                for pos in positions:
                    shares = float(pos.get('total_shares', 0))
                    avg_cost = float(pos.get('average_cost', 0))
                    asset_code = pos.get('asset_code')
                    asset_type = pos.get('asset_type')
                    current_price = pos.get('current_price')

                    if current_price:
                        total_value += shares * float(current_price)
                    else:
                        # Fetch current price from TuShare
                        price = self._get_current_price(asset_code, asset_type)
                        if price is not None:
                            total_value += shares * price
                        else:
                            # Price fetch failed - mark as incomplete, do NOT use avg_cost
                            logger.warning(f"Price unavailable for {asset_type}/{asset_code}, skipping from total_value")
                            missing_assets.append(f"{asset_type}:{asset_code}")
                            is_complete = False
                            # Skip this position from value calculation entirely
                            # We don't add anything to total_value for this position

                    total_cost += shares * avg_cost

                # If no valid prices could be fetched, skip this portfolio snapshot
                if total_value <= 0:
                    if missing_assets:
                        logger.warning(f"Skipping snapshot for portfolio {portfolio_id}: no valid prices, missing: {missing_assets}")
                        skipped_count += 1
                    continue

                # Calculate cumulative P&L (only meaningful if data is complete)
                cumulative_pnl = total_value - total_cost if is_complete else None
                cumulative_pnl_pct = ((total_value / total_cost) - 1) * 100 if (is_complete and total_cost > 0) else None

                # Calculate daily P&L
                daily_pnl = None
                daily_pnl_pct = None
                prev_snapshot = get_latest_snapshot(portfolio_id)
                if prev_snapshot and prev_snapshot['snapshot_date'] != snapshot_date:
                    prev_value = float(prev_snapshot.get('total_value', 0))
                    if prev_value > 0 and is_complete:
                        daily_pnl = total_value - prev_value
                        daily_pnl_pct = (daily_pnl / prev_value) * 100

                snapshot_data = {
                    'snapshot_date': snapshot_date,
                    'total_value': round(total_value, 2),
                    'total_cost': round(total_cost, 2),
                    'daily_pnl': round(daily_pnl, 2) if daily_pnl is not None else None,
                    'daily_pnl_pct': round(daily_pnl_pct, 2) if daily_pnl_pct is not None else None,
                    'cumulative_pnl': round(cumulative_pnl, 2) if cumulative_pnl is not None else None,
                    'cumulative_pnl_pct': round(cumulative_pnl_pct, 2) if cumulative_pnl_pct is not None else None,
                    'allocation': {},
                    # Metadata for data quality tracking (stored in allocation_json)
                    'is_complete': is_complete,
                    'missing_assets': missing_assets if missing_assets else None,
                }

                save_portfolio_snapshot(snapshot_data, portfolio_id)
                created_count += 1
                
                if not is_complete:
                    logger.warning(f"Portfolio {portfolio_id} snapshot created with incomplete data, missing: {missing_assets}")

            except Exception as e:
                error_count += 1
                logger.error(f"Error creating snapshot for portfolio {portfolio.get('id')}: {e}")

        print(f"Portfolio snapshots completed: {created_count} created, {skipped_count} skipped (no prices), {error_count} errors")

    def _get_current_price(self, asset_code: str, asset_type: str, retries: int = 2) -> Optional[float]:
        """Get current price for an asset using TuShare as primary source.
        
        Args:
            asset_code: Fund or stock code
            asset_type: 'fund' or 'stock'
            retries: Number of retry attempts on failure
            
        Returns:
            Current price/NAV as float, or None if unavailable
        """
        import time
        
        for attempt in range(retries + 1):
            try:
                if asset_type == 'fund':
                    # Use TuShare via data_source_manager for fund NAV
                    from src.data_sources.data_source_manager import get_fund_info_from_tushare
                    df = get_fund_info_from_tushare(asset_code)
                    if df is not None and not df.empty and '单位净值' in df.columns:
                        # DataFrame is sorted by date descending, first row is latest
                        latest_nav = df.iloc[0]['单位净值']
                        if latest_nav is not None:
                            return float(latest_nav)
                    return None
                else:
                    # Use existing stock quote API
                    from src.data_sources.akshare_api import get_stock_realtime_quote
                    quote = get_stock_realtime_quote(asset_code)
                    if quote and 'price' in quote:
                        return float(quote['price'])
                    return None
            except Exception as e:
                if attempt < retries:
                    logger.warning(f"Retry {attempt + 1}/{retries} for {asset_code}: {e}")
                    time.sleep(1)
                else:
                    logger.warning(f"Failed to get price for {asset_code} after {retries + 1} attempts: {e}")
                    return None
        return None

    def add_fund_jobs(self, fund: Dict):
        """Add Pre/Post market jobs for a single fund"""
        code = fund['code']
        # Ensure we have user_id, fallback to None (Admin/Legacy)
        user_id = fund.get('user_id') 
        
        # Pre-market
        if fund.get('pre_market_time'):
            try:
                hour, minute = fund['pre_market_time'].split(':')
                job_id = f"pre_{code}_{user_id}"
                self.scheduler.add_job(
                    self.run_analysis_task,
                    trigger=CronTrigger(hour=hour, minute=minute),
                    id=job_id,
                    args=[code, 'pre', user_id],
                    replace_existing=True
                )
                print(f"Scheduled PRE-market for {code} (User {user_id}) at {hour}:{minute}")
            except Exception as e:
                print(f"Error scheduling PRE task for {code}: {e}")

        # Post-market
        if fund.get('post_market_time'):
            try:
                hour, minute = fund['post_market_time'].split(':')
                job_id = f"post_{code}_{user_id}"
                self.scheduler.add_job(
                    self.run_analysis_task,
                    trigger=CronTrigger(hour=hour, minute=minute),
                    id=job_id,
                    args=[code, 'post', user_id],
                    replace_existing=True
                )
                print(f"Scheduled POST-market for {code} (User {user_id}) at {hour}:{minute}")
            except Exception as e:
                print(f"Error scheduling POST task for {code}: {e}")

    def remove_fund_jobs(self, code: str):
        """
        Remove jobs for a fund. 
        Note: This naive implementation removes jobs matching ID pattern.
        """
        # We need to find jobs starting with pre_{code}_ or post_{code}_
        # Iterate all jobs and match
        for job in self.scheduler.get_jobs():
            if job.id.startswith(f"pre_{code}_") or job.id.startswith(f"post_{code}_"):
                self.scheduler.remove_job(job.id)
                print(f"Removed job {job.id}")

    def run_analysis_task(self, fund_code: str, mode: str, user_id: Optional[int] = None):
        """Worker function"""
        # Check if today is a trading day
        if not trading_calendar.is_trading_day():
            print(f"Skipping {mode.upper()}-market task for fund {fund_code} - not a trading day")
            return

        print(f"Executing {mode.upper()}-market task for {fund_code} (User: {user_id})...")

        # Re-fetch fund data. Pass user_id if we want to be strict, or None to find by code globally.
        # But wait, code might not be unique globally anymore. We MUST filter by user_id if we have it.
        fund = get_fund_by_code(fund_code, user_id=user_id)
        
        if not fund or not fund.get('is_active'):
            print(f"Fund {fund_code} is inactive or deleted. Skipping.")
            return

        report = ""
        try:
            # Run analysis in thread to avoid blocking scheduler (though scheduler is threaded by default, good practice)
            # Actually apscheduler runs in thread/process pool executor.
            
            if mode == 'pre':
                analyst = PreMarketAnalyst()
                report = analyst.analyze_fund(fund)
            elif mode == 'post':
                analyst = PostMarketAnalyst()
                report = analyst.analyze_fund(fund)
            
            if report:
                save_report(report, mode, fund['name'], fund['code'], user_id=user_id)
                
        except Exception as e:
            logger.error(f"Task failed for {fund_code}: {e}")
            import traceback
            traceback.print_exc()

    def add_stock_jobs(self, stock: Dict):
        """Add Pre/Post market jobs for a single stock"""
        code = stock['code']
        user_id = stock.get('user_id')

        # Pre-market
        if stock.get('pre_market_time'):
            try:
                hour, minute = stock['pre_market_time'].split(':')
                job_id = f"stock_pre_{code}_{user_id}"
                self.scheduler.add_job(
                    self.run_stock_analysis_task,
                    trigger=CronTrigger(hour=hour, minute=minute),
                    id=job_id,
                    args=[code, 'pre', user_id],
                    replace_existing=True
                )
                print(f"Scheduled STOCK PRE-market for {code} (User {user_id}) at {hour}:{minute}")
            except Exception as e:
                print(f"Error scheduling STOCK PRE task for {code}: {e}")

        # Post-market
        if stock.get('post_market_time'):
            try:
                hour, minute = stock['post_market_time'].split(':')
                job_id = f"stock_post_{code}_{user_id}"
                self.scheduler.add_job(
                    self.run_stock_analysis_task,
                    trigger=CronTrigger(hour=hour, minute=minute),
                    id=job_id,
                    args=[code, 'post', user_id],
                    replace_existing=True
                )
                print(f"Scheduled STOCK POST-market for {code} (User {user_id}) at {hour}:{minute}")
            except Exception as e:
                print(f"Error scheduling STOCK POST task for {code}: {e}")

    def remove_stock_jobs(self, code: str):
        """Remove jobs for a stock."""
        for job in self.scheduler.get_jobs():
            if job.id.startswith(f"stock_pre_{code}_") or job.id.startswith(f"stock_post_{code}_"):
                self.scheduler.remove_job(job.id)
                print(f"Removed stock job {job.id}")

    def run_stock_analysis_task(self, stock_code: str, mode: str, user_id: Optional[int] = None):
        """Worker function for stock analysis"""
        # Check if today is a trading day
        if not trading_calendar.is_trading_day():
            print(f"Skipping STOCK {mode.upper()}-market task for {stock_code} - not a trading day")
            return

        print(f"Executing STOCK {mode.upper()}-market task for {stock_code} (User: {user_id})...")

        stock = get_stock_by_code(stock_code, user_id=user_id)

        if not stock or not stock.get('is_active'):
            print(f"Stock {stock_code} is inactive or deleted. Skipping.")
            return

        report = ""
        try:
            # Build stock_info dict for strategy
            stock_info = {
                "type": "stock",
                "code": stock['code'],
                "name": stock['name'],
                "sector": stock.get('sector', ''),
            }

            if mode == 'pre':
                analyst = PreMarketAnalyst()
                report = analyst.analyze_item(stock_info)
            elif mode == 'post':
                analyst = PostMarketAnalyst()
                report = analyst.analyze_item(stock_info)

            if report:
                save_stock_report(report, mode, stock['name'], stock['code'], user_id=user_id)

        except Exception as e:
            logger.error(f"Stock task failed for {stock_code}: {e}")
            import traceback
            traceback.print_exc()

# Global instance
scheduler_manager = SchedulerManager()