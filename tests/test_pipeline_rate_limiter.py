"""
Unit tests for the Rate Limiter.

These tests validate specific examples and edge cases for the rate limiter.
"""

import time
import pytest
from babel.pipeline.rate_limiter import RateLimiter


def test_rate_limiter_initialization():
    """Test that rate limiter initializes with correct default delay."""
    rate_limiter = RateLimiter()
    assert rate_limiter.min_delay == 4.0
    assert rate_limiter.last_call_time is None


def test_rate_limiter_custom_delay():
    """Test that rate limiter accepts custom delay."""
    rate_limiter = RateLimiter(min_delay_seconds=2.5)
    assert rate_limiter.min_delay == 2.5


def test_first_call_no_wait():
    """Test that first call doesn't wait (no previous call)."""
    rate_limiter = RateLimiter(min_delay_seconds=0.5)
    
    start_time = time.time()
    rate_limiter.wait_if_needed()
    elapsed = time.time() - start_time
    
    # Should return immediately (within 10ms)
    assert elapsed < 0.01


def test_minimum_delay_enforcement():
    """Test that minimum delay is enforced between calls."""
    min_delay = 0.5
    rate_limiter = RateLimiter(min_delay_seconds=min_delay)
    
    # First call
    rate_limiter.record_call()
    
    # Second call should wait
    start_time = time.time()
    rate_limiter.wait_if_needed()
    elapsed = time.time() - start_time
    
    # Should have waited approximately min_delay seconds
    # Allow 10ms tolerance for timing precision
    assert elapsed >= (min_delay - 0.01)


def test_no_wait_if_delay_already_passed():
    """Test that no wait occurs if minimum delay already passed."""
    min_delay = 0.2
    rate_limiter = RateLimiter(min_delay_seconds=min_delay)
    
    # First call
    rate_limiter.record_call()
    
    # Wait longer than min_delay
    time.sleep(min_delay + 0.1)
    
    # Second call should not wait
    start_time = time.time()
    rate_limiter.wait_if_needed()
    elapsed = time.time() - start_time
    
    # Should return immediately (within 10ms)
    assert elapsed < 0.01


def test_context_manager_usage():
    """Test that throttle context manager works correctly."""
    min_delay = 0.3
    rate_limiter = RateLimiter(min_delay_seconds=min_delay)
    
    call_times = []
    
    # Make two calls using context manager
    with rate_limiter.throttle():
        call_times.append(time.time())
    
    with rate_limiter.throttle():
        call_times.append(time.time())
    
    # Verify delay was enforced
    elapsed = call_times[1] - call_times[0]
    assert elapsed >= (min_delay - 0.01)


def test_context_manager_records_call_even_on_exception():
    """Test that context manager records call time even if exception occurs."""
    rate_limiter = RateLimiter(min_delay_seconds=0.2)
    
    # First call that raises exception
    try:
        with rate_limiter.throttle():
            raise ValueError("Test exception")
    except ValueError:
        pass
    
    # Verify call was recorded
    assert rate_limiter.last_call_time is not None
    first_call_time = rate_limiter.last_call_time
    
    # Second call should still enforce delay
    start_time = time.time()
    with rate_limiter.throttle():
        pass
    
    # Verify delay was enforced
    assert rate_limiter.last_call_time > first_call_time


def test_rapid_consecutive_calls():
    """Test that rapid consecutive calls are properly throttled."""
    min_delay = 0.2
    rate_limiter = RateLimiter(min_delay_seconds=min_delay)
    
    num_calls = 5
    call_times = []
    
    # Make rapid consecutive calls
    for _ in range(num_calls):
        with rate_limiter.throttle():
            call_times.append(time.time())
    
    # Verify all consecutive calls respect minimum delay
    for i in range(1, len(call_times)):
        elapsed = call_times[i] - call_times[i-1]
        assert elapsed >= (min_delay - 0.01), (
            f"Delay violated between calls {i-1} and {i}: {elapsed:.3f}s < {min_delay}s"
        )


def test_configurable_delays():
    """Test that different delay values work correctly."""
    delays = [0.1, 0.5, 1.0, 2.0]
    
    for min_delay in delays:
        rate_limiter = RateLimiter(min_delay_seconds=min_delay)
        
        # Make two calls
        call_times = []
        with rate_limiter.throttle():
            call_times.append(time.time())
        with rate_limiter.throttle():
            call_times.append(time.time())
        
        # Verify delay
        elapsed = call_times[1] - call_times[0]
        assert elapsed >= (min_delay - 0.01), (
            f"Delay {min_delay}s not enforced: elapsed {elapsed:.3f}s"
        )


def test_record_call_updates_timestamp():
    """Test that record_call updates the last_call_time."""
    rate_limiter = RateLimiter(min_delay_seconds=0.5)
    
    assert rate_limiter.last_call_time is None
    
    rate_limiter.record_call()
    first_time = rate_limiter.last_call_time
    assert first_time is not None
    
    time.sleep(0.1)
    
    rate_limiter.record_call()
    second_time = rate_limiter.last_call_time
    assert second_time > first_time


def test_wait_if_needed_with_no_previous_call():
    """Test that wait_if_needed handles None last_call_time correctly."""
    rate_limiter = RateLimiter(min_delay_seconds=0.5)
    
    # Should not raise exception and should return immediately
    start_time = time.time()
    rate_limiter.wait_if_needed()
    elapsed = time.time() - start_time
    
    assert elapsed < 0.01
    assert rate_limiter.last_call_time is None  # Should not modify state
