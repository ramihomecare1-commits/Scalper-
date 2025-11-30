import json
from typing import Dict

class PromptGenerator:
    @staticmethod
    def format_market_data(symbol: str, data: Dict) -> str:
        """
        Format consolidated market data into a prompt for the AI
        """
        try:
            prompt_parts = [f"Analyze the following market data for {symbol}:"]
            
            # 1. Current Market State
            ticker = data['market_data']['ticker']
            ob = data['market_data'].get('orderbook_analysis', {})
            
            prompt_parts.append(f"\n--- CURRENT STATE ---")
            prompt_parts.append(f"Price: {ticker.get('last')}")
            prompt_parts.append(f"24h Volume: {ticker.get('volume24h')}")
            
            if 'imbalance' in ob:
                prompt_parts.append(f"Order Book Imbalance: {ob.get('imbalance'):.2f} (-1 sell pressure, +1 buy pressure)")
                prompt_parts.append(f"Nearest Support: {ob.get('nearest_support')}")
                prompt_parts.append(f"Nearest Resistance: {ob.get('nearest_resistance')}")

            # 2. Technical Indicators per Timeframe
            prompt_parts.append(f"\n--- TIMEFRAME ANALYSIS ---")
            
            for tf, indicators in data.get('indicators', {}).items():
                if not indicators:
                    continue
                    
                prompt_parts.append(f"\n[{tf} Timeframe]")
                prompt_parts.append(f"RSI: {indicators.get('rsi', 'N/A'):.1f}")
                prompt_parts.append(f"Trend (MA5/10): {indicators.get('trend', 'N/A')}")
                prompt_parts.append(f"BB Position: {indicators.get('bb_position', 'N/A')}")
                prompt_parts.append(f"VWAP Distance: {indicators.get('vwap_dist', 0):.2f}%")
                
                # Volume info from candles
                candles = data['candles'].get(tf, [])
                if len(candles) >= 2:
                    last_vol = candles[-1]['volume']
                    prev_vol = candles[-2]['volume']
                    vol_change = ((last_vol - prev_vol) / prev_vol * 100) if prev_vol > 0 else 0
                    prompt_parts.append(f"Volume Change: {vol_change:.1f}%")

            prompt_parts.append(f"\nBased on this data, identify any immediate scalping opportunities.")
            
            return "\n".join(prompt_parts)
            
        except Exception as e:
            return f"Error formatting data: {str(e)}"
