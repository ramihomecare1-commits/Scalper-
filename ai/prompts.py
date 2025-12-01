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
import json
from typing import Dict

def create_analysis_prompt(symbol: str, market_data: Dict) -> str:
    """
    Create a prompt for AI analysis with market data
    """
    
    # Format indicators for each timeframe
    indicators_text = ""
    for tf, indicators in market_data.get('indicators', {}).items():
        indicators_text += f"\n{tf} Timeframe:\n"
        for key, value in indicators.items():
            if isinstance(value, (int, float)):
                indicators_text += f"  {key}: {value:.2f}\n"
            else:
                indicators_text += f"  {key}: {value}\n"
    
    # Format orderbook analysis
    ob_analysis = market_data.get('market_data', {}).get('orderbook_analysis', {})
    ob_text = f"""
Order Book Analysis:
  Imbalance: {ob_analysis.get('imbalance', 0):.2f}
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
