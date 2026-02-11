"""
Property-based tests for the Rate Limiter.

These tests validate universal correctness properties that should hold
across all valid executions of the rate limiter.
"""

import time
from hypothesis import given, strategies as st, settings, HealthCheck
from babel.pipeline.rate_limiter import RateLimiter


@settings(max_examples=20, suppress_health_check=[HealthCheck.too_slow], deadline=None)
@given(
    min_delay=st.floats(min_value=0.1, max_value=1.0),
    num_calls=st.integers(min_value=2, max_value=5)
)
def test_property_3_rate_limit_enforcement(min_delay, num_calls):
    """
    Feature: automation-pipeline, Property 3: Rate Limit Enforcement
    
    For any two consecutive API calls (including retries), the time elapsed
    between them should be at least the configured minimum delay.
    
    Validates: Requirements 3.1, 3.4, 15.5
    
    Args:
        min_delay: Minimum delay in seconds (0.1 to 2.0 for faster testing)
        num_calls: Number of consecutive calls to make (2 to 10)
    """
    # Create rate limiter with specified delay
    rate_limiter = RateLimiter(min_delay_seconds=min_delay)
    
    # Track call times
    call_times = []
    
    # Make consecutive calls using the throttle context manager
    for _ in range(num_calls):
        with rate_limiter.throttle():
            call_times.append(time.time())
    
    # Verify that all consecutive calls respect the minimum delay
    for i in range(1, len(call_times)):
        elapsed = call_times[i] - call_times[i-1]
        
        # Allow small tolerance for timing precision (10ms)
        tolerance = 0.01
        assert elapsed >= (min_delay - tolerance), (
            f"Rate limit violated: elapsed time {elapsed:.3f}s is less than "
            f"minimum delay {min_delay:.3f}s between calls {i-1} and {i}"
        )
