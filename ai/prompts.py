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
            
            # 1. Market Regime & State
            ticker = data['market_data']['ticker']
            ob = data['market_data'].get('orderbook_analysis', {})
            regime = data.get('regime', {})
            
            prompt_parts.append(f"\n--- MARKET REGIME ---")
            prompt_parts.append(f"State: {regime.get('regime', 'NEUTRAL')} ({regime.get('sub_type', 'SIDEWAYS')})")
            prompt_parts.append(f"Confidence: {regime.get('confidence', 0):.2f}")

            prompt_parts.append(f"\n--- CURRENT STATE ---")
            prompt_parts.append(f"Price: {ticker.get('last')}")
            
            if 'imbalance_10' in ob:
                prompt_parts.append(f"OB Imbalance (10): {ob.get('imbalance_10'):.2f} (-1=sell, +1=buy)")
                prompt_parts.append(f"OB Imbalance (20): {ob.get('imbalance_20'):.2f}")
                prompt_parts.append(f"Micro-Price: {ob.get('micro_price'):.2f}")
                prompt_parts.append(f"Total Liq (Bids/Asks): {ob.get('total_bid_liq')}/{ob.get('total_ask_liq')}")
                prompt_parts.append(f"S/R: {ob.get('nearest_support')} / {ob.get('nearest_resistance')}")
                prompt_parts.append(f"Spread: {ob.get('spread')} ({ob.get('spread_pct'):.3f}%)")

            # Sentiment Data
            sentiment = data['market_data'].get('sentiment', {})
            liquidations = data['market_data'].get('liquidations', [])
            
            if sentiment:
                prompt_parts.append(f"\n--- SENTIMENT & FLOW ---")
                if 'funding_rate' in sentiment:
                    fr = sentiment['funding_rate'].get('fundingRate', 0) * 100
                    prompt_parts.append(f"Funding Rate: {fr:.4f}%")
                
                if 'long_short_ratio' in sentiment:
                    ls = sentiment['long_short_ratio']
                    prompt_parts.append(f"Long/Short Ratio: {ls.get('longPct', 50)}% / {ls.get('shortPct', 50)}%")
                
                if 'taker_volume' in sentiment:
                    tv = sentiment['taker_volume']
                    prompt_parts.append(f"Taker Buy Ratio: {tv.get('buyRatio', 0.5):.2f}")
                
                if 'binance_ticker' in sentiment:
                    bin_last = sentiment['binance_ticker'].get('last', 0)
                    okx_last = ticker.get('last', 0)
                    if bin_last > 0 and okx_last > 0:
                        spread = okx_last - bin_last
                        spread_pct = (spread / okx_last) * 100
                        prompt_parts.append(f"OKX-Binance Spread: {spread_pct:+.3f}%")

            # 2. Technical Indicators per Timeframe
            prompt_parts.append(f"\n--- INDICATORS ---")
            
            for tf, indicators in data.get('indicators', {}).items():
                if not indicators:
                    continue
                    
                prompt_parts.append(f"\n[{tf}]")
                prompt_parts.append(f"RSI: {indicators.get('rsi', 'N/A'):.1f}")
                prompt_parts.append(f"ADX: {indicators.get('adx', 0):.1f} ({indicators.get('trend', 'NEUTRAL')})")
                
                # Ichimoku
                if 'ichimoku_signal' in indicators:
                    prompt_parts.append(f"Ichimoku: {indicators.get('ichimoku_pvcloud', 'N/A')} Cloud ({indicators.get('ichimoku_signal', 'NEUTRAL')})")

                prompt_parts.append(f"BB Pos: {indicators.get('bb_position', 'N/A')} (Bandwidth: {indicators.get('bb_bandwidth', 0):.4f})")
                prompt_parts.append(f"VWAP Dist: {indicators.get('vwap_dist', 0):.2f}%")
                prompt_parts.append(f"MACD Hist: {indicators.get('macd_histogram', 0):.4f} ({indicators.get('macd_crossover', 'NONE')})")
                
                # ATR
                atr_pct = indicators.get('atr_pct', 0)
                if atr_pct > 0:
                    prompt_parts.append(f"Volatility (ATR%): {atr_pct:.2f}%")
                
                # Volume
                prompt_parts.append(f"Vol Ratio: {indicators.get('vol_ratio', 1.0):.2f} ({indicators.get('vol_label', 'AVERAGE')})")

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
