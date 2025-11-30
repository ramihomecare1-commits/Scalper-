import okx.Trade as Trade
import okx.Account as Account
import okx.MarketData as MarketData
from config import Config
from utils.logger import log
from typing import Dict, Optional

class OKXClient:
    def __init__(self):
        flag = "1" if Config.OKX_DEMO_TRADING else "0"
        
        self.tradeAPI = Trade.TradeAPI(
            Config.OKX_API_KEY, 
            Config.OKX_SECRET_KEY, 
            Config.OKX_PASSPHRASE, 
            False, 
            flag
        )
        self.accountAPI = Account.AccountAPI(
            Config.OKX_API_KEY, 
            Config.OKX_SECRET_KEY, 
            Config.OKX_PASSPHRASE, 
            False, 
            flag
        )
        self.marketAPI = MarketData.MarketAPI(
            Config.OKX_API_KEY, 
            Config.OKX_SECRET_KEY, 
            Config.OKX_PASSPHRASE, 
            False, 
            flag
        )

    def get_balance(self, ccy: str = "USDT") -> float:
        """Get account balance for a specific currency"""
        try:
            result = self.accountAPI.get_account_balance(ccy=ccy)
            if result.get("code") == "0" and result.get("data"):
                return float(result["data"][0]["details"][0]["eq"])
            log.error(f"Error getting balance: {result}")
            return 0.0
        except Exception as e:
            log.error(f"Exception getting balance: {e}")
            return 0.0

    def place_order(self, instId: str, tdMode: str, side: str, ordType: str, sz: str, px: Optional[str] = None, slTriggerPx: Optional[str] = None, tpTriggerPx: Optional[str] = None) -> Dict:
        """
        Place an order
        tdMode: 'cash', 'cross', 'isolated'
        """
        try:
            args = {
                "instId": instId,
                "tdMode": tdMode,
                "side": side.lower(),
                "ordType": ordType.lower(),
                "sz": sz
            }
            if px:
                args["px"] = px
            
            # Attach SL/TP if provided (for OCO or simple attach depending on mode)
            # OKX allows attaching SL/TP to order placement
                return True

            result = self.tradeAPI.cancel_order(instId=instId, ordId=ordId)
            if result.get("code") == "0":
                log.info(f"Order {ordId} cancelled")
                return True
            log.error(f"Failed to cancel order: {result}")
            return False
        except Exception as e:
            log.error(f"Exception cancelling order: {e}")
            return False

    def get_positions(self, instType: str = "SWAP") -> Dict:
        """Get current positions"""
        try:
            result = self.accountAPI.get_positions(instType=instType)
            if result.get("code") == "0":
                return result.get("data", [])
            return []
        except Exception as e:
            log.error(f"Exception getting positions: {e}")
            return []
