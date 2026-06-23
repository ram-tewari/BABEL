"""
Rate limiter for API calls in BABEL pipeline.

This module provides rate limiting functionality to prevent API quota
exhaustion and ensure respectful API usage.
"""

import time
from contextlib import contextmanager
from typing import Optional


class RateLimiter:
    """
    Rate limiter for controlling API call frequency.
    
    Ensures a minimum delay between consecutive API calls.
    """

    def __init__(self, min_delay_seconds: float = 4.0):
        """
        Initialize rate limiter.
        
        Args:
            min_delay_seconds: Minimum delay between calls (default: 4.0s)
        """
        self.min_delay = min_delay_seconds
        self.last_call_time: Optional[float] = None

    def wait_if_needed(self) -> None:
        """
        Wait if minimum delay hasn't passed since last call.
        
        This method is idempotent - it only waits if necessary.
        """
        if self.last_call_time is None:
            return
        
        elapsed = time.time() - self.last_call_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)

    def record_call(self) -> None:
        """Record that a call was made (updates last_call_time)."""
        self.last_call_time = time.time()

    @contextmanager
    def throttle(self):
        """
        Context manager for rate-limited calls.
        
        Usage:
            with rate_limiter.throttle():
                make_api_call()
        """
        self.wait_if_needed()
        try:
            yield
        finally:
            self.record_call()