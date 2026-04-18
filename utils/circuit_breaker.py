import time
import asyncio
from enum import Enum
from typing import Dict, Optional, Callable, Any
from utils.logger import log

class CircuitState(Enum):
    CLOSED = "CLOSED"      # Normal operation
    OPEN = "OPEN"          # Error threshold reached, refusing calls
    HALF_OPEN = "HALF_OPEN" # Recovery testing

class CircuitBreaker:
    """
    Implements the Circuit Breaker pattern to protect the bot 
    from IP bans and cascading failures.
    """
    def __init__(
        self, 
        name: str, 
        failure_threshold: int = 5, 
        recovery_timeout: int = 60,
        half_open_max_calls: int = 2
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time: float = 0
        self.open_time: float = 0
        self.success_count = 0
        self.total_calls = 0
        
    def can_execute(self) -> bool:
        """Check if the circuit allows execution"""
        if self.state == CircuitState.CLOSED:
            return True
            
        if self.state == CircuitState.OPEN:
            # Check if cooldown period is over
            if time.time() - self.open_time >= self.recovery_timeout:
                log.info(f"Circuit {self.name} moving to HALF_OPEN state")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return True
            return False
            
        if self.state == CircuitState.HALF_OPEN:
            # Limit calls in half-open state
            return self.success_count < self.half_open_max_calls
            
        return False

    def record_success(self):
        """Record a successful operation"""
        self.total_calls += 1
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.half_open_max_calls:
                log.info(f"Circuit {self.name} moving to CLOSED state (Recovered)")
                self.reset()
        elif self.state == CircuitState.CLOSED:
            self.failures = 0 # Reset failure count on success when closed

    def record_failure(self):
        """Record a failed operation"""
        self.total_calls += 1
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            if self.failures >= self.failure_threshold:
                self._open_circuit()
        elif self.state == CircuitState.HALF_OPEN:
            # Any failure in half-open immediately re-opens the circuit
            self._open_circuit()

    def _open_circuit(self):
        """Transition to OPEN state"""
        if self.state != CircuitState.OPEN:
            log.error(f"Circuit {self.name} OPENED due to {self.failures} consecutive failures")
            from notifications.telegram_notifier import TelegramNotifier
            try:
                # Fire and forget notification
                asyncio.create_task(TelegramNotifier().notify_error(
                    f"🛑 <b>CIRCUIT BREAKER: {self.name}</b>\n"
                    f"The bot has triggered a safety circuit breaker and will pause requests to this service for {self.recovery_timeout}s."
                ))
            except:
                pass
            
        self.state = CircuitState.OPEN
        self.open_time = time.time()

    def reset(self):
        """Reset the circuit to CLOSED"""
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.success_count = 0
        log.info(f"Circuit {self.name} reset to CLOSED")

    def get_status(self) -> dict:
        """Get current status for dashboard"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failures": self.failures,
            "total_calls": self.total_calls,
            "last_failure": self.last_failure_time,
            "cooldown_remaining": max(0, self.recovery_timeout - (time.time() - self.open_time)) if self.state == CircuitState.OPEN else 0
        }

class CircuitBreakerManager:
    """Manages all circuit breakers in the system"""
    _instances: Dict[str, CircuitBreaker] = {}

    @classmethod
    def get_breaker(cls, name: str, **kwargs) -> CircuitBreaker:
        if name not in cls._instances:
            cls._instances[name] = CircuitBreaker(name, **kwargs)
        return cls._instances[name]

    @classmethod
    def get_all_statuses(cls) -> Dict[str, dict]:
        return {name: breaker.get_status() for name, breaker in cls._instances.items()}

def with_circuit_breaker(breaker_name: str):
    """Decorator for async functions to use a circuit breaker"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            breaker = CircuitBreakerManager.get_breaker(breaker_name)
            
            if not breaker.can_execute():
                log.warning(f"Circuit {breaker_name} is OPEN. Execution blocked for async {func.__name__}")
                return None
                
            try:
                result = await func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                log.error(f"Error in async {func.__name__} (Circuit {breaker_name}): {e}")
                raise e
        return wrapper
    return decorator

def with_circuit_breaker_sync(breaker_name: str):
    """Decorator for synchronous functions to use a circuit breaker"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            breaker = CircuitBreakerManager.get_breaker(breaker_name)
            
            if not breaker.can_execute():
                log.warning(f"Circuit {breaker_name} is OPEN. Execution blocked for sync {func.__name__}")
                return None
                
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as e:
                breaker.record_failure()
                log.error(f"Error in sync {func.__name__} (Circuit {breaker_name}): {e}")
                raise e
        return wrapper
    return decorator
