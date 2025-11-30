import json
from typing import Dict, List
from utils.logger import log
import os

class PerformanceTracker:
    def __init__(self, trade_log_file: str = "logs/trade_history.jsonl"):
        self.trade_log_file = trade_log_file

    def get_stats(self) -> Dict:
        """Calculate performance statistics from logs"""
        try:
            if not os.path.exists(self.trade_log_file):
                return {"error": "No trade history found"}

            trades = []
            with open(self.trade_log_file, "r") as f:
                for line in f:
                    trades.append(json.loads(line))

            if not trades:
                return {"total_trades": 0}

            # Simple stats without pandas
            symbols = list(set(t['symbol'] for t in trades if 'symbol' in t))
            actions = {}
            confidences = []
            
            for t in trades:
                action = t.get('action')
                if action:
                    actions[action] = actions.get(action, 0) + 1
                if 'confidence' in t:
                    confidences.append(t['confidence'])
            
            stats = {
                "total_trades": len(trades),
                "symbols": symbols,
                "actions": actions,
                "avg_confidence": sum(confidences) / len(confidences) if confidences else 0
            }
            
            return stats

        except Exception as e:
            log.error(f"Error calculating stats: {e}")
            return {}
