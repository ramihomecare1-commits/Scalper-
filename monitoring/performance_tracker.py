import json
import os
from typing import Dict, List
import pandas as pd
import numpy as np
from utils.logger import log

class PerformanceTracker:
    def __init__(self, trade_log_file: str = "logs/trade_history.jsonl"):
        self.trade_log_file = trade_log_file

    def _load_trades_df(self) -> pd.DataFrame:
        """Load and process trade logs into a merged DataFrame"""
        if not os.path.exists(self.trade_log_file):
            return pd.DataFrame()

        try:
            trades_raw = []
            with open(self.trade_log_file, "r") as f:
                for line in f:
                    trades_raw.append(json.loads(line))
            
            if not trades_raw:
                return pd.DataFrame()

            df_raw = pd.DataFrame(trades_raw)
            
            # Separate entries and exits to merge them
            entries = df_raw[df_raw['type'] == 'ENTRY'].copy()
            exits = df_raw[df_raw['type'] == 'EXIT'].copy()
            
            if entries.empty:
                return pd.DataFrame()
            
            # Merge on trade_id
            exit_cols = ['trade_id', 'exit_price', 'pnl', 'pnl_percent', 'duration', 'fees']
            for col in exit_cols:
                if col not in exits.columns:
                    exits[col] = np.nan
            
            # Remove any columns from entries that we want to take from exits
            # except for trade_id
            entries_filtered = entries.drop(columns=[c for c in exit_cols if c in entries.columns and c != 'trade_id'])

            df = pd.merge(
                entries_filtered, 
                exits[exit_cols], 
                on='trade_id', 
                how='left'
            )
            
            # Ensure pnl column exists in final df
            if 'pnl' not in df.columns:
                df['pnl'] = np.nan
            
            return df

        except Exception as e:
            log.error(f"Error loading trades DataFrame: {e}")
            return pd.DataFrame()

    def get_stats(self) -> Dict:
        """Calculate performance statistics from logs using pandas"""
        try:
            df = self._load_trades_df()
            
            if df.empty:
                return {"total_trades": 0}

            # Filter for completed trades (those with a pnl)
            completed_trades = df[df['pnl'].notna()].copy()
            
            if completed_trades.empty:
                return {
                    "total_trades": len(df),
                    "completed_trades": 0,
                    "avg_confidence": df['confidence'].mean() if 'confidence' in df else 0
                }

            # Basic Metrics
            total_trades = len(df)
            closed_trades = len(completed_trades)
            winners = completed_trades[completed_trades['pnl'] > 0]
            losers = completed_trades[completed_trades['pnl'] <= 0]
            
            win_rate = len(winners) / closed_trades if closed_trades > 0 else 0
            
            gross_profit = winners['pnl'].sum()
            gross_loss = abs(losers['pnl'].sum())
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else np.inf
            
            stats = {
                "total_trades": total_trades,
                "closed_trades": closed_trades,
                "win_rate": round(win_rate, 4),
                "profit_factor": round(profit_factor, 2),
                "total_net_pnl": round(completed_trades['pnl'].sum(), 2),
                "avg_trade_pnl": round(completed_trades['pnl'].mean(), 2),
                "expectancy": round(completed_trades['pnl'].mean(), 2),
                "max_win": round(completed_trades['pnl'].max(), 2),
                "max_loss": round(completed_trades['pnl'].min(), 2),
                "avg_confidence": round(df['confidence'].mean(), 2) if 'confidence' in df else 0,
                "symbols_traded": df['symbol'].unique().tolist()
            }
            
            return stats

        except Exception as e:
            log.error(f"Error calculating stats: {e}")
            return {}
