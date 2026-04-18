import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from utils.logger import log
import pandas as pd

class EquityTracker:
    def __init__(self, log_file: str = "logs/equity_history.jsonl"):
        self.log_file = log_file
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        self.current_equity = 0.0
        self.peak_equity = 0.0
        self.initial_equity = 0.0
        self._load_state()

    def _load_state(self):
        """Load state from history file if it exists"""
        if os.path.exists(self.log_file):
            try:
                history = self.get_equity_history()
                if history:
                    self.initial_equity = history[0].get('equity', 0.0)
                    self.current_equity = history[-1].get('equity', 0.0)
                    self.peak_equity = max(h.get('equity', 0.0) for h in history)
            except Exception as e:
                log.error(f"Error loading equity state: {e}")

    def record_equity(self, total_equity: float):
        """Record current equity to history"""
        try:
            if self.initial_equity == 0:
                self.initial_equity = total_equity
                self.peak_equity = total_equity
            
            self.current_equity = total_equity
            if total_equity > self.peak_equity:
                self.peak_equity = total_equity
            
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "equity": total_equity,
                "drawdown": self.get_current_drawdown(),
                "pnl_total": total_equity - self.initial_equity
            }
            
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
                
        except Exception as e:
            log.error(f"Error recording equity: {e}")

    def get_current_drawdown(self) -> float:
        """Calculate drawdown from peak"""
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - self.current_equity) / self.peak_equity

    def get_equity_history(self) -> List[Dict]:
        """Load equity history from file"""
        history = []
        if not os.path.exists(self.log_file):
            return history
            
        try:
            with open(self.log_file, "r") as f:
                for line in f:
                    history.append(json.loads(line))
        except Exception as e:
            log.error(f"Error reading equity history: {e}")
            
        return history

    def get_daily_returns(self) -> pd.Series:
        """Calculate daily returns for Sharpe/Sortino ratios via pandas"""
        history = self.get_equity_history()
        if not history:
            return pd.Series()
            
        df = pd.DataFrame(history)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df.set_index('timestamp', inplace=True)
        
        # Resample to daily equity (last value of the day)
        daily_equity = df['equity'].resample('D').last().ffill()
        daily_returns = daily_equity.pct_change().dropna()
        
        return daily_returns
