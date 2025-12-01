  Bid Pressure: {ob_analysis.get('bid_pressure', 0):.2f}
  Ask Pressure: {ob_analysis.get('ask_pressure', 0):.2f}
"""
    
    prompt = f"""You are a crypto scalping AI. Analyze this market data for {symbol} and respond with ONLY a JSON object, no other text.

CRITICAL: Your response must be VALID JSON ONLY. Do not include any explanations, markdown, or text outside the JSON object.

Market Data:
{indicators_text}
{ob_text}

Current Price: {market_data.get('market_data', {}).get('ticker', {}).get('last', 0)}

Respond with ONLY this exact JSON structure (no markdown, no explanations):
{{
    "action": "BUY" or "SELL" or "HOLD",
    "confidence": 0-100,
    "reasoning": "brief explanation",
    "entry_price": number,
    "stop_loss": number,
    "take_profit": number,
    "timeframe_confluence": ["1m", "5m"],
    "risk_level": "LOW" or "MEDIUM" or "HIGH"
}}

Rules:
- Only trade if confidence > 75
- Risk/Reward ratio must be at least 1.5:1
- Confirm signals across at least 2 timeframes
- RESPOND WITH JSON ONLY, NO OTHER TEXT"""
    
    return prompt
