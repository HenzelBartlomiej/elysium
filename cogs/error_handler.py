import discord
import traceback
import logging
from discord.ext import commands

logger = logging.getLogger('discord_bot.error_handler')

class ErrorHandler(commands.Cog):
    """Cog for handling command errors."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Event triggered when a command raises an error."""
        # Get the original error if it's wrapped in a CommandInvokeError
        error = getattr(error, 'original', error)
        
        if isinstance(error, commands.CommandNotFound):
            # Command not found
            await ctx.send(f"❌ That command doesn't exist. Use `{self.bot.command_prefix}help` to see available commands.")
        
        elif isinstance(error, commands.MissingRequiredArgument):
            # Missing arguments
            await ctx.send(f"❌ Missing required argument: `{error.param.name}`. Please check the command syntax.")
        
        elif isinstance(error, commands.BadArgument):
            # Invalid argument type
            await ctx.send(f"❌ Invalid argument provided. Please check the command syntax.")
        
        elif isinstance(error, commands.MissingPermissions):
            # User missing permissions
            missing_perms = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
            await ctx.send(f"❌ You're missing permissions to run this command: `{', '.join(missing_perms)}`")
        
        elif isinstance(error, commands.BotMissingPermissions):
            # Bot missing permissions
            missing_perms = [perm.replace('_', ' ').title() for perm in error.missing_permissions]
            await ctx.send(f"❌ I don't have the required permissions: `{', '.join(missing_perms)}`")
        
        elif isinstance(error, commands.CommandOnCooldown):
            # Command on cooldown
            await ctx.send(f"⏳ Command on cooldown. Try again in {error.retry_after:.1f} seconds.")
        
        elif isinstance(error, commands.NotOwner):
            # Not the bot owner
            await ctx.send("❌ This command can only be used by the bot owner.")
        
        elif isinstance(error, commands.NoPrivateMessage):
            # Command can't be used in DMs
            await ctx.send("❌ This command can't be used in private messages.")
        
        elif isinstance(error, commands.DisabledCommand):
            # Command is disabled
            await ctx.send("❌ This command is currently disabled.")
        
        else:
            # Unexpected error
            await ctx.send("❌ An unexpected error occurred. The error has been logged.")
            
            # Log the error
            logger.error(f"Command error in {ctx.command}:")
            logger.error(''.join(traceback.format_exception(type(error), error, error.__traceback__)))
            
            # Try to inform the owner about the error for critical issues
            if self.bot.owner_id:
                try:
                    owner = await self.bot.fetch_user(self.bot.owner_id)
                    error_traceback = ''.join(traceback.format_exception(type(error), error, error.__traceback__, limit=10))
                    error_message = f"Error in command `{ctx.command}` invoked by {ctx.author}:\n```py\n{error_traceback[:1900]}```"
                    await owner.send(error_message)
                except:
                    # If sending to owner fails, just continue - we've already logged the error
                    pass

async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))
