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

    def get_balance(self, currency: str = "USDT") -> float:
        """Get account balance for a specific currency"""
        try:
            if Config.DRY_RUN:
                log.info(f"DRY RUN: Simulating balance of 10000 {currency}")
                return 10000.0
            
            # Get account balance
            result = self.accountAPI.get_account_balance(ccy=currency)
            
            if result and result.get("code") == "0":
                data = result.get("data", [])
                if data and len(data) > 0:
                    details = data[0].get("details", [])
                    for detail in details:
                        if detail.get("ccy") == currency:
                            # Get available balance
                            avail_bal = detail.get("availBal", "0")
                            return float(avail_bal)
            
            log.warning(f"Could not get balance for {currency}, defaulting to 0")
            return 0.0
            
        except Exception as e:
            log.error(f"Exception getting balance: {e}")
            # In DRY_RUN mode, return simulated balance even on error
            if Config.DRY_RUN:
                return 10000.0
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
            
            # Attach SL/TP if provided
            if slTriggerPx:
                args["slTriggerPx"] = slTriggerPx
                args["slOrdPx"] = "-1"  # Market order for SL
            
            if tpTriggerPx:
                args["tpTriggerPx"] = tpTriggerPx
                args["tpOrdPx"] = "-1"  # Market order for TP

            log.info(f"Placing order: {args}")
            
            if Config.DRY_RUN:
                log.info("DRY RUN: Order not placed")
                return {"code": "0", "data": [{"ordId": "dry_run_id"}]}

            result = self.tradeAPI.place_order(**args)
            
            if result.get("code") == "0":
                log.info(f"Order placed successfully: {result['data'][0]['ordId']}")
                return result
            else:
                log.error(f"Order placement failed: {result}")
                return result

        except Exception as e:
            log.error(f"Exception placing order: {e}")
            return {"code": "-1", "msg": str(e)}

    def cancel_order(self, instId: str, ordId: str) -> bool:
        """Cancel an order"""
        try:
            if Config.DRY_RUN:
                log.info(f"DRY RUN: Cancel order {ordId}")
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

    def get_positions(self, instType: str = "SWAP") -> list:
        """Get current positions"""
        try:
            if Config.DRY_RUN:
                log.debug(f"DRY RUN: Returning empty positions list")
                return []
            
            result = self.accountAPI.get_positions(instType=instType)
            
            if result and result.get("code") == "0":
                positions = result.get("data", [])
                log.debug(f"Retrieved {len(positions)} positions from OKX")
                return positions
            
            log.warning(f"Could not get positions: {result}")
            return []
            
        except Exception as e:
            log.error(f"Exception getting positions: {e}")
            return []
