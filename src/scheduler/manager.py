import os
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
import logging
import asyncio
from datetime import datetime, date
from typing import Dict, Optional, Set
from src.storage.db import get_active_funds, get_fund_by_code, get_active_stocks, get_stock_by_code
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
        # Check if today is a trading day
        if not trading_calendar.is_trading_day():
            print(f"Skipping STOCK  - not a trading day")
            return

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