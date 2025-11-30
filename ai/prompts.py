import json
import pandas as pd
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
            ob = data['market_data']['orderbook']
            
            prompt_parts.append(f"\n--- CURRENT STATE ---")
            prompt_parts.append(f"Price: {ticker.get('last')}")
            prompt_parts.append(f"24h Volume: {ticker.get('volume24h')}")
            
            if 'imbalance' in ob:
                prompt_parts.append(f"Order Book Imbalance: {ob.get('imbalance'):.2f} (-1 sell pressure, +1 buy pressure)")
                prompt_parts.append(f"Nearest Support: {ob.get('nearest_support')}")
                prompt_parts.append(f"Nearest Resistance: {ob.get('nearest_resistance')}")

            # 2. Technical Indicators per Timeframe
            prompt_parts.append(f"\n--- TIMEFRAME ANALYSIS ---")
            
            for tf, df in data['candles'].items():
                if df.empty:
                    continue
                    
                last_row = df.iloc[-1]
                prev_row = df.iloc[-2] if len(df) > 1 else last_row
                
                prompt_parts.append(f"\n[{tf} Timeframe]")
                prompt_parts.append(f"Close: {last_row['close']}")
                prompt_parts.append(f"RSI: {last_row.get('rsi', 'N/A'):.1f}")
                
                # Trend
                sma5 = last_row.get('sma_5', 0)
                sma10 = last_row.get('sma_10', 0)
                trend = "BULLISH" if sma5 > sma10 else "BEARISH"
                prompt_parts.append(f"Trend (MA5/10): {trend}")
                
                # Bollinger Bands
                bb_pos = "INSIDE"
                if last_row['close'] > last_row.get('bb_high', float('inf')): bb_pos = "ABOVE UPPER"
                elif last_row['close'] < last_row.get('bb_low', 0): bb_pos = "BELOW LOWER"
                prompt_parts.append(f"BB Position: {bb_pos}")
                
                # Volume Change
                vol_change = (last_row['volume'] - prev_row['volume']) / prev_row['volume'] * 100 if prev_row['volume'] > 0 else 0
                prompt_parts.append(f"Volume Change: {vol_change:.1f}%")

            prompt_parts.append(f"\nBased on this data, identify any immediate scalping opportunities.")
            
            return "\n".join(prompt_parts)
            
        except Exception as e:
            return f"Error formatting data: {str(e)}"
