import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    # System Configuration
    ENV = os.getenv("ENV", "development")
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    DRY_RUN = os.getenv("DRY_RUN", "True").lower() == "true"
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    # OKX API Configuration
    OKX_API_KEY = os.getenv("OKX_API_KEY")
    OKX_SECRET_KEY = os.getenv("OKX_SECRET_KEY")
    OKX_PASSPHRASE = os.getenv("OKX_PASSPHRASE")
    # Use OKX Demo Trading URL by default for safety
    OKX_DEMO_TRADING = os.getenv("OKX_DEMO_TRADING", "True").lower() == "true"
    
    # DeepSeek / AI Configuration
    DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
    DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat") # or specific R1 model name if available via API
    
    # Trading Configuration
    TRADING_PAIRS = os.getenv("TRADING_PAIRS", "BTC-USDT,ETH-USDT").split(",")
    TIMEFRAMES = ["1m", "5m", "10m", "1H"]
    
    # Risk Management
    LEVERAGE = int(os.getenv("LEVERAGE", "3"))
    POSITION_SIZE_PERCENT = float(os.getenv("POSITION_SIZE_PERCENT", "0.02")) # 2%
    MAX_LOSS_PER_TRADE_PERCENT = float(os.getenv("MAX_LOSS_PER_TRADE_PERCENT", "0.01")) # 1% of account
    RISK_REWARD_RATIO = float(os.getenv("RISK_REWARD_RATIO", "1.5"))
    
    # Render / Deployment
    PORT = int(os.getenv("PORT", "10000"))

    @classmethod
    def validate(cls):
        """Validate critical configuration"""
        if not cls.OKX_API_KEY or not cls.OKX_SECRET_KEY:
            raise ValueError("Missing OKX API credentials")
        if not cls.DEEPSEEK_API_KEY:
            raise ValueError("Missing DeepSeek API key")
