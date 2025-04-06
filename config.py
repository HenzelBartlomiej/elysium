import os
from dotenv import load_dotenv
import logging

# Set up logging
logger = logging.getLogger('discord_bot.config')

# Load environment variables from .env file as fallback
load_dotenv()

# Discord bot configuration
# Prioritize environment variables from Replit secrets
DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN", os.getenv("DISCORD_TOKEN", ""))
BOT_PREFIX = os.environ.get("BOT_PREFIX", os.getenv("BOT_PREFIX", "!"))
BOT_OWNER_ID = os.environ.get("BOT_OWNER_ID", os.getenv("BOT_OWNER_ID", None))

# Log token status (without revealing it)
if DISCORD_TOKEN:
    logger.info("Discord token found")
else:
    logger.warning("No Discord token found - bot will not connect to Discord")

if BOT_OWNER_ID and str(BOT_OWNER_ID).isdigit():
    BOT_OWNER_ID = int(BOT_OWNER_ID)
else:
    BOT_OWNER_ID = None

# List of cogs to load
COGS = [
    "cogs.basic_commands",
    "cogs.error_handler",
    "cogs.auto_response",
    "cogs.ai_chat"
]

# Flask configuration
FLASK_SECRET_KEY = os.environ.get("SESSION_SECRET", os.getenv("SESSION_SECRET", "dev-secret-key"))

# Command configuration
DISABLED_COMMANDS = os.environ.get("DISABLED_COMMANDS", os.getenv("DISABLED_COMMANDS", "")).split(",")
