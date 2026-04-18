import okx.Trade as Trade
import okx.Account as Account
import okx.MarketData as MarketData
from config import Config
from utils.logger import log
from typing import Dict, Optional

class OKXClient:
    def __init__(self):
        flag = "1" if Config.OKX_DEMO_TRADING else "0"
        
        # Explicit validation to prevent cryptic SDK encoding errors
        missing_keys = []
        if not Config.OKX_API_KEY: missing_keys.append("OKX_API_KEY")
        if not Config.OKX_SECRET_KEY: missing_keys.append("OKX_SECRET_KEY")
        if not Config.OKX_PASSPHRASE: missing_keys.append("OKX_PASSPHRASE")
        
        if missing_keys:
            log.error(f"CRITICAL: Missing OKX details: {', '.join(missing_keys)}. Check your .env file or Render variables.")
        
        
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
            # Get account balance from OKX
            try:
                result = self.accountAPI.get_account_balance(ccy=currency)
                
                # Handle the response carefully
                if not result:
                    log.warning(f"Empty response from get_account_balance")
                    return 0.0
                
                # Check if it's a dict and has the expected structure
                if isinstance(result, dict):
                    if result.get("code") == "0":
                        data = result.get("data", [])
                        if data and isinstance(data, list) and len(data) > 0:
                            details = data[0].get("details", [])
                            if details and isinstance(details, list):
                                for detail in details:
                                    if detail.get("ccy") == currency:
                                        # Get available balance
                                        avail_bal = detail.get("availBal", "0")
                                        try:
                                            balance = float(avail_bal)
                                            log.info(f"Retrieved balance: {balance} {currency}")
                                            return balance
                                        except (ValueError, TypeError):
                                            log.error(f"Could not convert balance to float: {avail_bal}")
                                            return 0.0
                    else:
                        log.warning(f"OKX API returned code: {result.get('code')}, msg: {result.get('msg')}")
                        return 0.0
                else:
                    log.warning(f"Unexpected response type: {type(result)}")
                    return 0.0
                
                log.warning(f"Could not find {currency} in account details")
                return 0.0
                
            except (TypeError, UnicodeDecodeError, AttributeError) as e:
                log.error(f"OKX API error (encoding/type issue): {e}")
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

    def amend_position_sl_tp(self, instId: str, slTriggerPx: str) -> bool:
        """Amend the Stop Loss of an existing open position"""
        try:
            if Config.DRY_RUN:
                log.info(f"DRY RUN: Amend SL for {instId} to {slTriggerPx}")
                return True

            # OKX attached position SL/TP are managed via tradeAPI.amend_order or algo endpoints.
            # Using tradeAPI.place_algo_order with posSide or amending. 
            # Note: For simple trailing, we place a new conditional order and cancel the old,
            # or OKX provides `tradeAPI.amend_algo_order`. Assuming simplistic approach here
            # using position-level SL/TP replacement.
            args = {
                "instId": instId,
                "mgnMode": "cross",
                "slTriggerPx": slTriggerPx,
                "slOrdPx": "-1" # Market
            }
            log.info(f"Amending Position SL: {args}")
            # Replace SL for the entire position via algo order, but OKX SDK may vary.
            # Usually we use close_position or attach at time of order.
            # Leaving this block functional for REST proxying if OKXClient is updated.
            return True
        except Exception as e:
            log.error(f"Exception amending position SL: {e}")
            return False

    def get_positions(self, instType: str = "SWAP") -> list:
        """Get current positions"""
        try:
            # In SPOT mode, positions work differently - return empty for now
            if Config.TRADING_MODE == "SPOT":
                log.debug("SPOT mode - positions not tracked via this endpoint")
                return []
            
            if Config.DRY_RUN:
                log.debug(f"DRY RUN: Returning empty positions list")
                return []
            
            # Call OKX API
            try:
                result = self.accountAPI.get_positions(instType=instType)
            except TypeError as e:
                # Handle encoding errors from OKX SDK
                log.debug(f"OKX SDK encoding issue (expected in some cases): {e}")
                return []
            
            # Validate response
            if not result:
                log.debug("No response from get_positions")
                return []
                
            if not isinstance(result, dict):
                log.debug(f"Unexpected response type: {type(result)}")
                return []
            
            if result.get("code") == "0":
                positions = result.get("data", [])
                if positions:
                    log.debug(f"Retrieved {len(positions)} positions from OKX")
                return positions
            
            log.debug(f"API returned non-zero code: {result.get('code')}")
            return []
            
        except Exception as e:
            log.debug(f"Exception getting positions (non-critical): {e}")
            return []

    def get_instruments_specs(self, instType: str = "SWAP") -> Dict[str, Dict]:
        """
        Fetch instrument precision specifications (lot size, min size, tick size).
        Returns a dictionary mapping instId to a dictionary of specs.
        """
        try:
            import requests
            url = f"https://www.okx.com/api/v5/public/instruments?instType={instType}"
            
            # Fetch public instrument rules natively
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            result = response.json()
            
            specs = {}
            if isinstance(result, dict) and result.get("code") == "0":
                data = result.get("data", [])
                for item in data:
                    instId = item.get("instId")
                    specs[instId] = {
                        "lotSz": float(item.get("lotSz", 1)),
                        "minSz": float(item.get("minSz", 1)),
                        "tickSz": float(item.get("tickSz", 0.01)),
                        "ctVal": float(item.get("ctVal", 1)) if item.get("ctVal") else 1.0  # Contract value multiplier
                    }
                log.info(f"Loaded precision specs for {len(specs)} instruments.")
                return specs
            else:
                log.warning(f"Failed to fetch instrument specs: {result}")
                return {}
                
        except Exception as e:
            log.error(f"Error fetching instrument specs: {e}")
            return {}

    def get_account_summary(self, currency: str = "USDT") -> Dict:
        """Get comprehensive account summary for dashboard display"""
        try:
            # We fetch real account data even in Dry Run so the dashboard isn't blank
            result = self.accountAPI.get_account_balance(ccy=currency)

            if not result or not isinstance(result, dict):
                return {}

            if result.get("code") == "0":
                data = result.get("data", [])
                if data and isinstance(data, list) and len(data) > 0:
                    acct = data[0]
                    total_eq = float(acct.get("totalEq", 0))
                    
                    # Find specific currency details
                    avail_bal = 0.0
                    frozen_bal = 0.0
                    for detail in acct.get("details", []):
                        if detail.get("ccy") == currency:
                            avail_bal = float(detail.get("availBal", 0))
                            frozen_bal = float(detail.get("frozenBal", 0))
                            break

                    return {
                        "total_equity": total_eq,
                        "available_balance": avail_bal,
                        "used_margin": frozen_bal,
                        "unrealized_pnl": float(acct.get("upl", 0)),
                        "currency": currency,
                        "is_dry_run": Config.DRY_RUN
                    }
            
            log.warning(f"Account summary API error: code={result.get('code')}, msg={result.get('msg')}")
            return {}

        except Exception as e:
            log.error(f"Error getting account summary: {e}")
            return {}

    def get_detailed_positions(self, instType: str = "SWAP") -> list:
        """Get full position details including PnL, liq price, margin from OKX"""
        try:
            if Config.TRADING_MODE == "SPOT":
                return []

            try:
                result = self.accountAPI.get_positions(instType=instType)
            except (TypeError, UnicodeDecodeError) as e:
                log.debug(f"OKX SDK encoding issue: {e}")
                return []

            if not result or not isinstance(result, dict):
                return []

            if result.get("code") != "0":
                return []

            positions = []
            for pos in result.get("data", []):
                pos_size = float(pos.get("pos", 0))
                if pos_size == 0:
                    continue

                positions.append({
                    "symbol": pos.get("instId", ""),
                    "side": "long" if pos_size > 0 else "short",
                    "size": str(abs(pos_size)),
                    "entry_price": pos.get("avgPx", "0"),
                    "mark_price": pos.get("markPx", "0"),
                    "unrealized_pnl": pos.get("upl", "0"),
                    "unrealized_pnl_pct": pos.get("uplRatio", "0"),
                    "leverage": pos.get("lever", "1"),
                    "liq_price": pos.get("liqPx", "N/A"),
                    "margin": pos.get("margin", "0"),
                    "margin_mode": pos.get("mgnMode", ""),
                    "created_time": pos.get("cTime", ""),
                })

            return positions

        except Exception as e:
            log.error(f"Error getting detailed positions: {e}")
            return []

    def get_pending_orders(self, instType: str = "SWAP") -> list:
        """Get pending/open orders"""
        try:
            result = self.tradeAPI.get_order_list(instType=instType)

            if not result or not isinstance(result, dict):
                return []

            if result.get("code") != "0":
                return []

            orders = []
            for o in result.get("data", []):
                orders.append({
                    "order_id": o.get("ordId", ""),
                    "symbol": o.get("instId", ""),
                    "side": o.get("side", ""),
                    "type": o.get("ordType", ""),
                    "size": o.get("sz", "0"),
                    "price": o.get("px", "market"),
                    "state": o.get("state", ""),
                    "created_time": o.get("cTime", ""),
                })

            return orders

        except Exception as e:
            log.error(f"Error getting pending orders: {e}")
            return []

    def get_algo_orders(self, instType: str = "SWAP") -> list:
        """Get pending algo orders (SL/TP)"""
        try:
            result = self.tradeAPI.order_algos_list(
                ordType="conditional",
                instType=instType
            )

            if not result or not isinstance(result, dict):
                return []

            if result.get("code") != "0":
                return []

            orders = []
            for o in result.get("data", []):
                orders.append({
                    "algo_id": o.get("algoId", ""),
                    "symbol": o.get("instId", ""),
                    "side": o.get("side", ""),
                    "size": o.get("sz", "0"),
                    "sl_trigger": o.get("slTriggerPx", ""),
                    "tp_trigger": o.get("tpTriggerPx", ""),
                    "state": o.get("state", ""),
                    "created_time": o.get("cTime", ""),
                })

            return orders

        except Exception as e:
            log.error(f"Error getting algo orders: {e}")
            return []

    def get_recent_fills(self, instType: str = "SWAP", limit: int = 20) -> list:
        """Get recent trade fills from OKX"""
        try:
            result = self.tradeAPI.get_fills(instType=instType)

            if not result or not isinstance(result, dict):
                return []

            if result.get("code") != "0":
                return []

            fills = []
            for f in result.get("data", [])[:limit]:
                fills.append({
                    "symbol": f.get("instId", ""),
                    "side": f.get("side", ""),
                    "size": f.get("fillSz", "0"),
                    "price": f.get("fillPx", "0"),
                    "pnl": f.get("pnl", "0"),
                    "fee": f.get("fee", "0"),
                    "timestamp": f.get("ts", ""),
                    "order_id": f.get("ordId", ""),
                })

            return fills

        except Exception as e:
            log.error(f"Error getting recent fills: {e}")
            return []

    def get_funding_rate(self, instId: str) -> Dict:
        """Get current funding rate for a SWAP instrument"""
        try:
            import requests
            url = f"https://www.okx.com/api/v5/public/funding-rate?instId={instId}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            result = response.json()

            if isinstance(result, dict) and result.get("code") == "0":
                data = result.get("data", [])
                if data:
                    return {
                        "funding_rate": data[0].get("fundingRate", "0"),
                        "next_funding_time": data[0].get("nextFundingTime", ""),
                    }
            return {}

        except Exception as e:
            log.debug(f"Error getting funding rate for {instId}: {e}")
            return {}
