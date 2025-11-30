import sys
from loguru import logger
from config import Config
import os

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# Remove default handler
logger.remove()

# Add console handler
logger.add(
    sys.stderr,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
    level=Config.LOG_LEVEL,
)

# Add file handler for all logs
logger.add(
    "logs/app.log",
    rotation="500 MB",
    retention="10 days",
    level="INFO",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
)

# Add file handler for errors
logger.add(
    "logs/error.log",
    rotation="100 MB",
    retention="10 days",
    level="ERROR",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
)

# Add separate file handler for trades
logger.add(
    "logs/trades.log",
    rotation="100 MB",
    retention="30 days",
    level="INFO",
    filter=lambda record: "TRADE" in record["extra"],
    format="{time:YYYY-MM-DD HH:mm:ss} | {message}",
)

def setup_logger():
    """Initialize logger configuration"""
    logger.info(f"Logger initialized. Level: {Config.LOG_LEVEL}")
    return logger

# Create a global logger instance
log = logger
