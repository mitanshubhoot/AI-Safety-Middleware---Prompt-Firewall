"""Circuit breaker pattern for resilience."""
import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Optional

from src.utils.logging import get_logger
from src.utils.metrics import errors_total

logger = get_logger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreakerError(Exception):
    """Exception raised when circuit is open."""

    pass


class CircuitBreaker:
    """Circuit breaker for handling service failures gracefully."""

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: str = "default",
    ):
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exception: Exception type that triggers circuit
            name: Circuit breaker name for logging
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
        
        logger.info(
            "circuit_breaker_initialized",
            name=name,
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
        )

    def _should_attempt_reset(self) -> bool:
        """Check if circuit should attempt to reset.

        Returns:
            True if enough time has passed since last failure
        """
        if self.last_failure_time is None:
            return False
        
        time_since_failure = datetime.utcnow() - self.last_failure_time
        return time_since_failure >= timedelta(seconds=self.recovery_timeout)

    def _on_success(self) -> None:
        """Handle successful call."""
        if self.state == CircuitState.HALF_OPEN:
            logger.info("circuit_closed", name=self.name)
            self.state = CircuitState.CLOSED
        
        self.failure_count = 0
        self.last_failure_time = None

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.utcnow()
        
        errors_total.labels(
            error_type="circuit_breaker_failure",
            component=self.name,
        ).inc()
        
        if self.failure_count >= self.failure_threshold:
            if self.state != CircuitState.OPEN:
                logger.warning(
                    "circuit_opened",
                    name=self.name,
                    failure_count=self.failure_count,
                )
                self.state = CircuitState.OPEN

    async def call(
        self,
        func: Callable,
        *args: Any,
        fallback: Optional[Callable] = None,
        **kwargs: Any,
    ) -> Any:
        """Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            fallback: Optional fallback function if circuit is open
            **kwargs: Keyword arguments for func

        Returns:
            Result of func or fallback

        Raises:
            CircuitBreakerError: If circuit is open and no fallback provided
        """
        # Check if circuit is open
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info("circuit_half_open_attempting_reset", name=self.name)
                self.state = CircuitState.HALF_OPEN
            else:
                # Circuit still open
                logger.warning(
                    "circuit_open_request_rejected",
                    name=self.name,
                    failure_count=self.failure_count,
                )
                
                if fallback:
                    logger.debug("using_fallback", name=self.name)
                    return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
                
                raise CircuitBreakerError(
                    f"Circuit breaker '{self.name}' is OPEN"
                )
        
        # Attempt to call function
        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        
        except self.expected_exception as e:
            self._on_failure()
            logger.error(
                "circuit_breaker_call_failed",
                name=self.name,
                error=str(e),
                state=self.state.value,
            )
            
            # If we have a fallback, use it
            if fallback:
                logger.debug("using_fallback_after_failure", name=self.name)
                return await fallback(*args, **kwargs) if asyncio.iscoroutinefunction(fallback) else fallback(*args, **kwargs)
            
            raise

    def get_state(self) -> dict:
        """Get current circuit breaker state.

        Returns:
            Dictionary with circuit state information
        """
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "failure_threshold": self.failure_threshold,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }

    def reset(self) -> None:
        """Manually reset circuit breaker."""
        logger.info("circuit_manually_reset", name=self.name)
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = None


class CircuitBreakerRegistry:
    """Registry for managing multiple circuit breakers."""

    def __init__(self):
        """Initialize circuit breaker registry."""
        self.breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
    ) -> CircuitBreaker:
        """Get existing or create new circuit breaker.

        Args:
            name: Circuit breaker name
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds before attempting recovery
            expected_exception: Exception type that triggers circuit

        Returns:
            CircuitBreaker instance
        """
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                name=name,
            )
        
        return self.breakers[name]

    def get_all_states(self) -> dict[str, dict]:
        """Get states of all circuit breakers.

        Returns:
            Dictionary of circuit breaker states
        """
        return {
            name: breaker.get_state()
            for name, breaker in self.breakers.items()
        }

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self.breakers.values():
            breaker.reset()


# Global registry
_registry = CircuitBreakerRegistry()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
) -> CircuitBreaker:
    """Get circuit breaker from global registry.

    Args:
        name: Circuit breaker name
        failure_threshold: Number of failures before opening
        recovery_timeout: Seconds before attempting recovery
        expected_exception: Exception type that triggers circuit

    Returns:
        CircuitBreaker instance
    """
    return _registry.get_or_create(
        name=name,
        failure_threshold=failure_threshold,
        recovery_timeout=recovery_timeout,
        expected_exception=expected_exception,
    )
