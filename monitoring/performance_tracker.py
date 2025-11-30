import pandas as pd
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

            df = pd.DataFrame(trades)
            
            # This is a simplified view. Real PnL requires tracking exits.
            # Assuming we have 'pnl' field if we updated logs after close, 
            # or we just track number of entries for now.
            
            stats = {
                "total_trades": len(df),
                "symbols": df['symbol'].unique().tolist(),
                "actions": df['action'].value_counts().to_dict(),
                "avg_confidence": df['confidence'].mean() if 'confidence' in df else 0
            }
            
            return stats

        except Exception as e:
            log.error(f"Error calculating stats: {e}")
            return {}
