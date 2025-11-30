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

    def log_trade(self, trade_data: Dict[str, Any]):
        """
        Log a trade with full context to JSONL file
        """
        try:
            entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "symbol": trade_data.get("symbol"),
                "action": trade_data.get("action"),
                "price": trade_data.get("entry_price"),
                "quantity": trade_data.get("quantity"),
                "reasoning": trade_data.get("reasoning"),
                "confidence": trade_data.get("confidence"),
                "market_snapshot": self._sanitize_snapshot(trade_data.get("market_snapshot", {})),
                "ai_analysis": trade_data.get("ai_analysis", {})
            }
            
            with open(self.log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
                
            log.info(f"Trade logged to {self.log_file}")
            
        except Exception as e:
            log.error(f"Error logging trade: {e}")

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
