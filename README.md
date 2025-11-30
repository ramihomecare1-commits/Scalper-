# AI Crypto Scalping Bot

A high-frequency scalping bot powered by DeepSeek R1 AI and OKX API.

## Features

- **Multi-Timeframe Analysis**: Monitors 1m, 5m, 10m, and 1h candles simultaneously.
- **AI Decision Engine**: Uses DeepSeek R1 to analyze market structure and generate signals.
- **Risk Management**: Strict 2-3% position sizing, dynamic SL/TP, and trailing stops.
- **Real-time Data**: WebSocket integration for low-latency market updates.
- **Order Book Analysis**: Analyzes L2 depth for support/resistance and imbalance.

## Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Configuration**
   Copy `.env.example` to `.env` and fill in your credentials:
   ```bash
   cp .env.example .env
   ```
   
   Required credentials:
   - OKX API Key, Secret, Passphrase (Demo or Real)
   - DeepSeek API Key

3. **Run the Bot**
   ```bash
   python bot.py
   ```

## Configuration Options

- `DRY_RUN`: Set to `True` to simulate trades without executing them.
- `OKX_DEMO_TRADING`: Set to `True` to use OKX Demo network.
- `TRADING_PAIRS`: Comma-separated list of pairs (e.g., "BTC-USDT,ETH-USDT").
- `LEVERAGE`: Default leverage to use (e.g., 3).

## Project Structure

- `ai/`: DeepSeek integration and prompt engineering.
- `analysis/`: Technical indicators and order book analysis.
- `data/`: OKX WebSocket and REST clients, data normalization.
- `risk/`: Position sizing and risk management logic.
- `trading/`: Order execution and management.
- `monitoring/`: Trade logging and performance tracking.
- `utils/`: Logging and helper functions.

## Disclaimer

This software is for educational purposes only. Use at your own risk. Crypto trading involves significant risk of loss.
