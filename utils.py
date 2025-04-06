import logging
from config import DISABLED_COMMANDS

logger = logging.getLogger('discord_bot.utils')

def is_command_disabled(command_name):
    """Check if a command is disabled in the configuration."""
    return command_name in DISABLED_COMMANDS
