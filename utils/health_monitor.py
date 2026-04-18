import time
import psutil
import os
from typing import Dict, List, Any
from utils.logger import log
from utils.circuit_breaker import CircuitBreakerManager

class HealthMonitor:
    """
    Centralized health monitoring for the bot system.
    Tracks uptime, connection status, error trends, and resource usage.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(HealthMonitor, cls).__new__(cls)
            cls._instance._init()
        return cls._instance
        
    def _init(self):
        self.start_time = time.time()
        self.errors = []
        self.max_error_log = 50
        self.connection_states = {
            "okx_ws": False,
            "binance_ws": False,
            "okx_rest": True
        }
        self.latencies = {}
        self.reconnect_counts = {
            "okx_ws": 0,
            "binance_ws": 0
        }
        
    def record_error(self, component: str, message: str, critical: bool = False):
        """Record an error event"""
        error_event = {
            "time": time.time(),
            "component": component,
            "message": message,
            "critical": critical
        }
        self.errors.append(error_event)
        if len(self.errors) > self.max_error_log:
            self.errors.pop(0)
            
        if critical:
            log.critical(f"HEALTH ALERT [{component}]: {message}")

    def update_connection_status(self, component: str, status: bool):
        """Update the connection status of a component"""
        self.connection_states[component] = status
        if not status:
            log.warning(f"Connection lost for {component}")
        else:
            log.info(f"Connection active for {component}")

    def record_reconnect(self, component: str):
        """Record a reconnection attempt"""
        self.reconnect_counts[component] = self.reconnect_counts.get(component, 0) + 1

    def update_latency(self, component: str, latency_ms: float):
        """Update recorded latency for a component"""
        self.latencies[component] = latency_ms

    def get_system_metrics(self) -> dict:
        """Get host system metrics"""
        try:
            process = psutil.Process(os.getpid())
            return {
                "cpu_percent": psutil.cpu_percent(),
                "memory_usage_mb": process.memory_info().rss / (1024 * 1024),
                "threads": process.num_threads(),
                "uptime_days": (time.time() - self.start_time) / 86400
            }
        except Exception:
            return {}

    def get_full_report(self) -> dict:
        """Generate a complete health report for the dashboard"""
        now = time.time()
        return {
            "uptime_seconds": int(now - self.start_time),
            "status": "healthy" if all(self.connection_states.values()) else "degraded",
            "connections": self.connection_states,
            "reconnect_counts": self.reconnect_counts,
            "latencies": self.latencies,
            "circuits": CircuitBreakerManager.get_all_statuses(),
            "recent_errors": self.errors[-10:], # Last 10 for quick view
            "system": self.get_system_metrics()
        }

# Singleton instance
health_monitor = HealthMonitor()
