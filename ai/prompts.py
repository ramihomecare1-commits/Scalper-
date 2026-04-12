import json
from typing import Dict

class PromptGenerator:
    @staticmethod
    def format_market_data(symbol: str, data: Dict) -> str:
        """
        Format consolidated market data into a prompt for the AI.
        Kept concise to minimize token usage while maximizing signal quality.
        """
        try:
            prompt_parts = [f"Analyze {symbol} for a scalping opportunity:"]
            
            # 1. Current Market State
            ticker = data['market_data']['ticker']
            ob = data['market_data'].get('orderbook_analysis', {})
            
            prompt_parts.append(f"\n--- CURRENT STATE ---")
            prompt_parts.append(f"Price: {ticker.get('last')}")
            prompt_parts.append(f"24h Vol: {ticker.get('volume24h')}")
            
            if 'imbalance' in ob:
                prompt_parts.append(f"OB Imbalance: {ob.get('imbalance'):.2f} (-1=sell, +1=buy)")
                prompt_parts.append(f"Support: {ob.get('nearest_support')}")
                prompt_parts.append(f"Resistance: {ob.get('nearest_resistance')}")
                prompt_parts.append(f"Spread: {ob.get('spread')}")

            # 2. Technical Indicators per Timeframe
            prompt_parts.append(f"\n--- INDICATORS ---")
            
            for tf, indicators in data.get('indicators', {}).items():
                if not indicators:
                    continue
                    
                prompt_parts.append(f"\n[{tf}]")
                prompt_parts.append(f"RSI: {indicators.get('rsi', 'N/A'):.1f}")
                prompt_parts.append(f"Trend (MA5/10): {indicators.get('trend', 'N/A')}")
                prompt_parts.append(f"BB: {indicators.get('bb_position', 'N/A')}")
                prompt_parts.append(f"VWAP Dist: {indicators.get('vwap_dist', 0):.2f}%")
                
                # MACD
                prompt_parts.append(f"MACD: {indicators.get('macd', 0):.4f}, Signal: {indicators.get('macd_signal', 0):.4f}, Crossover: {indicators.get('macd_crossover', 'NONE')}")
                
                # ATR (volatility)
                atr = indicators.get('atr', 0)
                if atr > 0:
                    current_price = ticker.get('last', 0)
                    atr_pct = (atr / current_price * 100) if current_price else 0
                    prompt_parts.append(f"ATR: {atr:.2f} ({atr_pct:.2f}% of price)")
                
                # Volume change
                candles = data['candles'].get(tf, [])
                if len(candles) >= 2:
                    last_vol = candles[-1]['volume']
                    prev_vol = candles[-2]['volume']
                    vol_change = ((last_vol - prev_vol) / prev_vol * 100) if prev_vol > 0 else 0
                    prompt_parts.append(f"Vol Change: {vol_change:.1f}%")

            # 3. Recent Price Action (last 5 candles from the primary timeframe)
            primary_tf = list(data.get('candles', {}).keys())[0] if data.get('candles') else None
            if primary_tf:
                candles = data['candles'].get(primary_tf, [])
                if len(candles) >= 5:
                    prompt_parts.append(f"\n--- LAST 5 CANDLES ({primary_tf}) ---")
                    for c in candles[-5:]:
                        body = "GREEN" if c['close'] > c['open'] else "RED"
                        prompt_parts.append(f"  {body} O:{c['open']:.2f} H:{c['high']:.2f} L:{c['low']:.2f} C:{c['close']:.2f} V:{c['volume']:.0f}")

            # JSON-only instruction
            prompt_parts.append(f"\nRespond with ONLY a valid JSON object:")
            prompt_parts.append(f'{{"action":"BUY"|"SELL"|"HOLD","confidence":0-100,"reasoning":"brief text","entry_price":num,"stop_loss":num,"take_profit":num,"risk_level":"LOW"|"MEDIUM"|"HIGH"}}')
            
            return "\n".join(prompt_parts)
            
        except Exception as e:
            return f"Error formatting data: {str(e)}"
