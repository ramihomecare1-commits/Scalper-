import json
from datetime import datetime
from typing import Dict, Any
from utils.logger import log
import os

class TradeLogger:
    def __init__(self, log_file: str = "logs/trade_history.jsonl"):
        self.log_file = log_file
        # Ensure directory exists
        os.makedirs(os.path.dirname(log_file), exist_ok=True)

    def log_entry(self, entry_data: Dict[str, Any]):
        """
        Log a trade entry with full context.
        """
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "ENTRY",
                "trade_id": entry_data.get("trade_id"),
                "symbol": entry_data.get("symbol"),
                "side": entry_data.get("side"),
                "price": entry_data.get("price"),
                "quantity": entry_data.get("quantity"),
                "confidence": entry_data.get("confidence"),
                "reasoning": entry_data.get("reasoning"),
                "market_snapshot": self._sanitize_snapshot(entry_data.get("market_snapshot", {})),
                "ai_analysis": entry_data.get("ai_analysis", {})
            }
            self._write_to_log(entry)
            log.info(f"Trade Entry logged: {entry_data.get('symbol')} {entry_data.get('side')}")
        except Exception as e:
            log.error(f"Error logging trade entry: {e}")

    def log_exit(self, exit_data: Dict[str, Any]):
        """
        Log a trade exit.
        """
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": "EXIT",
                "trade_id": exit_data.get("trade_id"),
                "symbol": exit_data.get("symbol"),
                "exit_price": exit_data.get("exit_price"),
                "pnl": exit_data.get("pnl"),
                "pnl_percent": exit_data.get("pnl_percent"),
                "duration": exit_data.get("duration"),
                "fees": exit_data.get("fees", 0)
            }
            self._write_to_log(entry)
            log.info(f"Trade Exit logged: {exit_data.get('symbol')} PnL: {exit_data.get('pnl')}")
        except Exception as e:
            log.error(f"Error logging trade exit: {e}")

    def _write_to_log(self, data: Dict[str, Any]):
        with open(self.log_file, "a") as f:
            f.write(json.dumps(data) + "\n")

    def log_trade(self, trade_data: Dict[str, Any]):
        """Legacy support for simple logging"""
        self._write_to_log(trade_data)

    def _sanitize_snapshot(self, snapshot: Dict) -> Dict:
        """Remove heavy data like full orderbooks from snapshot for logging"""
        if not snapshot:
            return {}
        
        clean = snapshot.copy()
        # Keep only top levels of OB if present
        if "market_data" in clean and "orderbook" in clean["market_data"]:
            ob = clean["market_data"]["orderbook"]
            if "bids" in ob:
                ob["bids"] = ob["bids"][:5] # Keep top 5
            if "asks" in ob:
                ob["asks"] = ob["asks"][:5]
        
        # Simplify candles to just last few
        if "candles" in clean:
            clean["candles"] = {k: "DataFrame_Summary" for k in clean["candles"]}
            
        return clean
