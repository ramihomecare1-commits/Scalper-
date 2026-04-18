import asyncio
from typing import List, Dict, Optional
from data.okx_client import OKXClient
from risk.portfolio_risk import portfolio_risk_manager
from utils.logger import log
from config import Config
from monitoring.equity_tracker import EquityTracker

class PositionMonitor:
    """
    Actively monitors open positions on OKX and ensures local state sync.
    Feeds data to PortfolioRiskManager and StopLossManager.
    """
    def __init__(self, client: Optional[OKXClient] = None):
        self.client = client or OKXClient()
        self.equity_tracker = EquityTracker()
        self.positions = []
        self._last_sync_time = 0
        self._sync_interval = 5  # Seconds between syncs

    async def sync_positions(self) -> List[Dict]:
        """
        Fetch positions from OKX and update internal state.
        """
        try:
            # OKX endpoint returns detailed position info
            raw_positions = self.client.get_detailed_positions()
            
            # Map raw data to a standardized format if needed
            synced_positions = []
            for pos in raw_positions:
                # Add human-friendly direction
                pos['direction'] = "LONG" if float(pos.get('size', 0)) > 0 else "SHORT"
                synced_positions.append(pos)
            
            self.positions = synced_positions
            self._last_sync_time = asyncio.get_event_loop().time()
            
            # Check portfolio health automatically after sync
            acct_summary = self.client.get_account_summary()
            total_equity = acct_summary.get('total_equity', 0)
            
            if total_equity > 0:
                self.equity_tracker.record_equity(total_equity)
                health_ok, message = portfolio_risk_manager.check_portfolio_health(total_equity, self.positions)
                if not health_ok:
                    log.critical(f"Portfolio health check failed: {message}")
                    # In a production bot, we might emit a KILL_ALL_TRADES signal here
            
            return self.positions

        except Exception as e:
            log.error(f"Error syncing positions: {e}")
            return self.positions

    def get_active_positions(self) -> List[Dict]:
        """Returns the last known positions."""
        return self.positions

    def get_position_for_symbol(self, symbol: str) -> Optional[Dict]:
        """Fetch a specific symbol's position."""
        for pos in self.positions:
            if pos.get('symbol') == symbol:
                return pos
        return None

    async def monitor_loop(self):
        """Background loop to keep positions synced."""
        log.info("Starting Position Monitor loop...")
        while True:
            await self.sync_positions()
            await asyncio.sleep(self._sync_interval)

# Global singleton instance if needed for centralized monitoring
position_monitor = PositionMonitor()
