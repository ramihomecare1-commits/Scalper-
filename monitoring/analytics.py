import os
from typing import Dict, List, Optional
from monitoring.performance_tracker import PerformanceTracker
from monitoring.equity_tracker import EquityTracker
from utils.logger import log
import numpy as np

class AnalyticsAgent:
    def __init__(self, 
                 trade_log: str = "logs/trade_history.jsonl", 
                 equity_log: str = "logs/equity_history.jsonl"):
        self.performance = PerformanceTracker(trade_log)
        self.equity = EquityTracker(equity_log)

    def get_full_status(self) -> Dict:
        """Get consolidated analytics status"""
        try:
            stats = self.performance.get_stats()
            
            # Add Sharpe Ratio if we have enough returns data
            returns = self.equity.get_daily_returns()
            sharpe = self.calculate_sharpe_ratio(returns)
            sortino = self.calculate_sortino_ratio(returns)
            
            status = {
                **stats,
                "current_drawdown": round(self.equity.get_current_drawdown(), 4),
                "sharpe_ratio": round(sharpe, 2),
                "sortino_ratio": round(sortino, 2),
                "equity_curve": self.equity.get_equity_history()[-100:] # Last 100 points
            }
            
            return status
        except Exception as e:
            log.error(f"Error getting full analytics status: {e}")
            return {}

    def calculate_sharpe_ratio(self, returns, risk_free_rate: float = 0.02) -> float:
        """Calculate annualized Sharpe Ratio"""
        if len(returns) < 2:
            return 0.0
        
        # Daily risk free rate
        daily_rf = (1 + risk_free_rate) ** (1/365) - 1
        
        excess_returns = returns - daily_rf
        if excess_returns.std() == 0:
            return 0.0
            
        sharpe = (excess_returns.mean() / excess_returns.std()) * np.sqrt(365)
        return sharpe

    def calculate_sortino_ratio(self, returns, risk_free_rate: float = 0.02) -> float:
        """Calculate annualized Sortino Ratio (Downside Deviation)"""
        if len(returns) < 2:
            return 0.0
            
        daily_rf = (1 + risk_free_rate) ** (1/365) - 1
        excess_returns = returns - daily_rf
        
        downside_returns = excess_returns[excess_returns < 0]
        if len(downside_returns) < 2 or downside_returns.std() == 0:
            return 0.0
            
        sortino = (excess_returns.mean() / downside_returns.std()) * np.sqrt(365)
        return sortino
