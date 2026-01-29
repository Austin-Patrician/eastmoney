"""
Rate Limiter for TuShare API calls.

Implements per-interface rate limiting to ensure we don't exceed API rate limits.
Each TuShare interface has its own independent rate limit based on user points level.
"""
import os
import time
import threading
from typing import Optional, Dict


class TuShareRateLimiter:
    """
    Thread-safe rate limiter for TuShare API with per-interface independent limits.

    TuShare rate limits are PER INTERFACE based on user points level:
    - 120 points: 50 calls/minute per interface
    - 2000+ points: 200 calls/minute per interface
    - 5000+ points: 500 calls/minute per interface
    - 10000+ points: 1000 calls/minute per interface

    Each interface (fund_nav, fund_manager, daily, etc.) has its own independent quota.
    Some interfaces have special lower limits regardless of points level.
    """

    # Predefined tier configurations based on TuShare points
    TIER_CONFIGS = {
        120: {'calls_per_minute': 50, 'name': '基础版'},
        2000: {'calls_per_minute': 200, 'name': '标准版'},
        5000: {'calls_per_minute': 500, 'name': '高级版'},
        10000: {'calls_per_minute': 1000, 'name': '专业版'},
    }

    # Per-interface special limits (lower than tier limit)
    # These apply regardless of user points level
    INTERFACE_SPECIAL_LIMITS = {
        'moneyflow': 100,  # Stock-level money flow: 100 calls/minute
        'daily_basic': 100,  # Daily basic indicators: 100 calls/minute
        'stk_limit': 100,  # Limit list: 100 calls/minute
        'moneyflow_hsgt': 100,  # Northbound flow: 100 calls/minute
        # Add more interfaces with special limits as needed
    }

    def __init__(self, points: Optional[int] = None, safety_margin: Optional[float] = None):
        """
        Initialize rate limiter with tier-based configuration.

        Args:
            points: User points level (auto-detected from env if not provided)
            safety_margin: Safety margin ratio (0.9 = use 90% of quota)
        """
        # Auto-detect points from environment
        if points is None:
            points = self._detect_points_from_env()

        # Auto-detect safety margin from environment
        if safety_margin is None:
            safety_margin = self._detect_safety_margin_from_env()

        # Get tier configuration
        config = self._get_tier_config(points)

        # Store configuration
        self.points = points
        self.tier_name = config['name']
        self.tier_limit = config['calls_per_minute']  # Base limit per interface
        self.safety_margin = safety_margin
        self.time_window = 60.0

        # For backward compatibility
        self.max_calls = int(self.tier_limit * safety_margin)
        self.raw_limit = self.tier_limit

        # Per-interface rate limiting state (each interface tracked independently)
        self.interface_calls: Dict[str, list] = {}  # interface_name -> list of timestamps
        self.lock = threading.Lock()  # Single lock for all operations

    def _detect_points_from_env(self) -> int:
        """
        Detect TuShare points level from environment variable.

        Returns:
            Points level (default: 2000)
        """
        points_str = os.getenv('TUSHARE_POINTS', '2000')
        try:
            return int(points_str)
        except ValueError:
            print(f"[RateLimiter] Invalid TUSHARE_POINTS value: {points_str}, using default 2000")
            return 2000

    def _detect_safety_margin_from_env(self) -> float:
        """
        Detect safety margin from environment variable.

        Returns:
            Safety margin ratio (default: 0.9)
        """
        margin_str = os.getenv('TUSHARE_RATE_LIMIT_MARGIN', '0.9')
        try:
            margin = float(margin_str)
            if 0.5 <= margin <= 1.0:
                return margin
            else:
                print(f"[RateLimiter] Safety margin {margin} out of range [0.5, 1.0], using default 0.9")
                return 0.9
        except ValueError:
            print(f"[RateLimiter] Invalid TUSHARE_RATE_LIMIT_MARGIN value: {margin_str}, using default 0.9")
            return 0.9

    def _get_tier_config(self, points: int) -> dict:
        """
        Get tier configuration based on points level.

        Args:
            points: User points level

        Returns:
            Tier configuration dict
        """
        # Find the highest tier that user qualifies for
        for tier_points in sorted(self.TIER_CONFIGS.keys(), reverse=True):
            if points >= tier_points:
                return self.TIER_CONFIGS[tier_points]

        # Default to lowest tier
        return self.TIER_CONFIGS[120]

    def _get_interface_limit(self, interface: str) -> int:
        """
        Get the rate limit for a specific interface.

        Args:
            interface: Interface name (e.g., 'fund_nav', 'daily')

        Returns:
            Max calls per minute for this interface (with safety margin applied)
        """
        # Check if interface has a special (lower) limit
        special_limit = self.INTERFACE_SPECIAL_LIMITS.get(interface)
        if special_limit:
            raw_limit = min(special_limit, self.tier_limit)
        else:
            raw_limit = self.tier_limit

        return int(raw_limit * self.safety_margin)

    def acquire(self, interface: Optional[str] = None, timeout: Optional[float] = None) -> bool:
        """
        Acquire permission to make an API call for a specific interface.

        Each interface has its own independent rate limit quota.
        Blocks until permission is granted or timeout expires.

        Args:
            interface: Interface name (e.g., 'fund_nav', 'daily'). Required for proper limiting.
            timeout: Maximum time to wait in seconds (None = wait forever)

        Returns:
            True if permission granted, False if timeout
        """
        # Use 'unknown' if interface not specified (backward compatibility)
        if not interface:
            interface = 'unknown'

        start_time = time.time()
        max_calls = self._get_interface_limit(interface)

        while True:
            with self.lock:
                now = time.time()

                # Initialize interface tracking if needed
                if interface not in self.interface_calls:
                    self.interface_calls[interface] = []

                # Clean up old calls for this interface
                self.interface_calls[interface] = [
                    t for t in self.interface_calls[interface]
                    if now - t < self.time_window
                ]

                current_calls = len(self.interface_calls[interface])

                # Check if we can make a call
                if current_calls < max_calls:
                    self.interface_calls[interface].append(now)
                    return True

                # Calculate wait time
                oldest_call = min(self.interface_calls[interface])
                wait_time = self.time_window - (now - oldest_call) + 0.1

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
                wait_time = min(wait_time, timeout - elapsed)

            # Wait before retrying
            print(f"[RateLimiter] Interface '{interface}' rate limit reached ({current_calls}/{max_calls}), waiting {wait_time:.1f}s...")
            time.sleep(wait_time)

    def get_stats(self, interface: Optional[str] = None) -> dict:
        """
        Get current rate limiter statistics.

        Args:
            interface: Optional interface name to get interface-specific stats

        Returns:
            Dict with current usage statistics
        """
        with self.lock:
            now = time.time()

            # Calculate total calls across all interfaces for backward compatibility
            total_calls = 0
            for iface, calls in self.interface_calls.items():
                self.interface_calls[iface] = [t for t in calls if now - t < self.time_window]
                total_calls += len(self.interface_calls[iface])

            stats = {
                'tier_name': self.tier_name,
                'points': self.points,
                'tier_limit': self.tier_limit,
                'safety_margin': self.safety_margin,
                'max_calls': self.max_calls,  # backward compatibility
                'raw_limit': self.raw_limit,  # backward compatibility
                'time_window': self.time_window,
                'active_interfaces': len(self.interface_calls),
                # Backward compatibility fields
                'current_calls': total_calls,
                'utilization': total_calls / (self.max_calls * max(1, len(self.interface_calls))) * 100 if self.max_calls > 0 else 0,
            }

            # Add interface-specific stats if requested
            if interface:
                if interface not in self.interface_calls:
                    self.interface_calls[interface] = []

                self.interface_calls[interface] = [
                    t for t in self.interface_calls[interface]
                    if now - t < self.time_window
                ]

                interface_max = self._get_interface_limit(interface)
                current_calls = len(self.interface_calls[interface])

                stats['interface'] = interface
                stats['interface_current_calls'] = current_calls
                stats['interface_max_calls'] = interface_max
                stats['interface_utilization'] = (
                    current_calls / interface_max * 100
                    if interface_max > 0 else 0
                )

            # Add summary of all active interfaces
            interface_summary = {}
            for iface, calls in self.interface_calls.items():
                calls = [t for t in calls if now - t < self.time_window]
                self.interface_calls[iface] = calls
                iface_max = self._get_interface_limit(iface)
                interface_summary[iface] = {
                    'current': len(calls),
                    'max': iface_max,
                    'utilization': len(calls) / iface_max * 100 if iface_max > 0 else 0
                }
            stats['interfaces'] = interface_summary

            return stats

    def reset(self, interface: Optional[str] = None):
        """
        Reset the rate limiter.

        Args:
            interface: Optional interface to reset. If None, resets all interfaces.
        """
        with self.lock:
            if interface:
                self.interface_calls[interface] = []
            else:
                self.interface_calls = {}


# Global rate limiter instance for TuShare API
# Automatically configured based on environment variables
tushare_rate_limiter = TuShareRateLimiter()
