import os
import logging
import asyncio
import discord
from discord.ext import commands
from config import BOT_PREFIX, DISCORD_TOKEN, COGS
from utils import is_command_disabled

# Set up logging for the bot
logger = logging.getLogger('discord_bot')

# Create a bot instance with command prefix
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.members = True

bot = commands.Bot(command_prefix=BOT_PREFIX, intents=intents, help_command=None)

# Bot status tracker for web dashboard
# bot_status = {
#     "is_ready": False,
#     "guild_count": 0,
#     "user_count": 0,
#     "latency": 0,
#     "commands_used": 0,
#     "last_command": None,
#     "uptime_start": None
# }

@bot.event
async def on_ready():
    """Event triggered when the bot has connected to Discord."""
    logger.info(f"Bot connected as {bot.user.name} (ID: {bot.user.id})")
    
    # Update status
    # bot_status["is_ready"] = True
    # bot_status["guild_count"] = len(bot.guilds)
    # bot_status["user_count"] = sum(guild.member_count for guild in bot.guilds)
    
    # Set bot activity
    activity = discord.Activity(
        type=discord.ActivityType.listening,
        name=f"{BOT_PREFIX}ask | {BOT_PREFIX}help"
    )
    await bot.change_presence(activity=activity)
    
    # Load cogs
    logger.info("Loading cogs...")
    for cog in COGS:
        try:
            await bot.load_extension(cog)
            logger.info(f"Loaded cog: {cog}")
        except Exception as e:
            logger.error(f"Failed to load cog {cog}: {e}")

@bot.event
async def on_message(message):
    """Event triggered when a message is received."""
    # Ignore messages from bots (including itself)
    # if message.author.bot:
    #     return
    
    # Process commands if message starts with prefix
    if message.author.bot == False and message.content.startswith(BOT_PREFIX):
        command_name = message.content.split()[0][len(BOT_PREFIX):]
        
        # Check if command is disabled
        if is_command_disabled(command_name):
            await message.channel.send(f"⚠️ The command `{command_name}` is currently disabled.")
            return
        
        # Update command statistics
        # bot_status["commands_used"] += 1
        # bot_status["last_command"] = {
        #     "name": command_name,
        #     "user": message.author.name,
        #     "timestamp": message.created_at.isoformat()
        # }
    
    # Process commands
    # await bot.process_commands(message)

@bot.event
async def on_guild_join(guild):
    """Event triggered when the bot joins a new server."""
    logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
    
    # Update server count
    # bot_status["guild_count"] = len(bot.guilds)
    # bot_status["user_count"] = sum(guild.member_count for guild in bot.guilds)

@bot.event
async def on_guild_remove(guild):
    """Event triggered when the bot is removed from a server."""
    logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
    
    # Update server count
    # bot_status["guild_count"] = len(bot.guilds)
    # bot_status["user_count"] = sum(guild.member_count for guild in bot.guilds)

# def get_bot_status():
#     """Return the current status of the bot for the web dashboard."""
#     if bot.is_ready():
#         # Update latency
#         bot_status["latency"] = bot.latency * 1000  # Convert to ms
    
#     return bot_status

def get_ai_stats():
    """Get AI chat statistics for the web dashboard."""
    if not bot.is_ready():
        return {
            "total_questions": 0,
            "total_resets": 0,
            "active_conversations": 0,
            "top_users": [],
            "is_ready": False
        }
    
    try:
        ai_cog = bot.get_cog("AIChat")
        if ai_cog:
            return ai_cog.get_ai_stats()
        else:
            return {
                "total_questions": 0,
                "total_resets": 0,
                "active_conversations": 0,
                "top_users": [],
                "kb_documents": 0,
                "kb_names": [],
                "cog_loaded": False
            }
    except Exception as e:
        logger.error(f"Error getting AI stats: {str(e)}")
        return {
            "total_questions": 0,
            "total_resets": 0,
            "active_conversations": 0,
            "top_users": [],
            "kb_documents": 0,
            "kb_names": [],
            "error": str(e)
        }

def run_bot():
    """Start the Discord bot."""
    import datetime
    # bot_status["uptime_start"] = datetime.datetime.now().isoformat()
    
    # Run the bot with the token from config
    if not DISCORD_TOKEN:
        logger.critical("No Discord token found! Make sure you've set it in your .env file.")
        return
    
    try:
        asyncio.run(bot.start(DISCORD_TOKEN))
    except discord.errors.LoginFailure:
        logger.critical("Invalid Discord token. Please check your .env file.")
    except KeyboardInterrupt:
        logger.info("Bot shutting down...")
    except Exception as e:
        logger.critical(f"An error occurred: {e}")
