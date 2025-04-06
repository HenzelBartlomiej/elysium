from unittest import skip
import discord
import logging
from discord.ext import commands

logger = logging.getLogger('discord_bot.basic_commands')

class BasicCommands(commands.Cog):
    """Cog that handles basic bot commands."""
    
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command(name="ping", help="Check if the bot is responsive")
    async def ping(self, ctx):
        """Responds with the bot's latency."""
        latency = round(self.bot.latency * 1000)
        await ctx.send(f"🏓 Pong! Latency: {latency}ms")
        logger.debug(f"Ping command used by {ctx.author.name}, latency: {latency}ms")
    
    @commands.command(name="help", help="Shows a list of available commands")
    async def help_command(self, ctx, command_name=None):
        """Displays help information for commands."""
        prefix = self.bot.command_prefix
        
        if command_name:
            # Show help for a specific command
            command = self.bot.get_command(command_name)
            if command:
                embed = discord.Embed(
                    title=f"Help: {prefix}{command.name}",
                    description=command.help or "No description available.",
                    color=discord.Color.blue()
                )
                
                # Add usage if the command has parameters
                signature = command.signature
                if signature:
                    embed.add_field(
                        name="Usage", 
                        value=f"`{prefix}{command.name} {signature}`",
                        inline=False
                    )
                
                await ctx.send(embed=embed)
            else:
                await ctx.send(f"❌ Command `{command_name}` not found. Type `{prefix}help` for a list of commands.")
        else:
            # Show general help with all commands
            embed = discord.Embed(
                title="Bot Commands",
                description=f"Use `{prefix}help <command>` for more details about a specific command.",
                color=discord.Color.blue()
            )
            
            # Group commands by cog
            cogs = {}
            for command in self.bot.commands:
                if command.hidden:
                    continue
                
                cog_name = command.cog_name or "No Category"
                if cog_name not in cogs:
                    cogs[cog_name] = []
                
                cogs[cog_name].append(command)
            
            # Add fields for each cog
            for cog_name, cmds in cogs.items():
                command_list = "\n".join([f"`{prefix}{cmd.name}` - {cmd.help}" for cmd in cmds])
                
                # Use custom title for AI Chat cog
                if cog_name == "AIChat":
                    # Split AI commands into chat and knowledge base categories
                    ai_chat_cmds = []
                    # kb_cmds = []
                    
                    for cmd in cmds:
                        if cmd.name.startswith("kb_"):
                            # kb_cmds.append(cmd)
                            continue
                        else:
                            ai_chat_cmds.append(cmd)
                    
                    # AI Chat commands
                    ai_chat_list = "\n".join([f"`{prefix}{cmd.name}` - {cmd.help}" for cmd in ai_chat_cmds])
                    embed.add_field(
                        name="🤖 AI Chat Commands",
                        value=ai_chat_list + "\n\nPowered by Google Gemini AI",
                        inline=False
                    )
                    
                    # Knowledge Base commands
                    # if kb_cmds:
                    #     kb_list = "\n".join([f"`{prefix}{cmd.name}` - {cmd.help}" for cmd in kb_cmds])
                    #     embed.add_field(
                    #         name="📚 Knowledge Base Commands",
                    #         value=kb_list + "\n\nUse knowledge bases with `!ask using:kb_name your question`",
                    #         inline=False
                    #     )
                else:
                    embed.add_field(
                        name=cog_name,
                        value=command_list,
                        inline=False
                    )
            
            await ctx.send(embed=embed)
        
        logger.debug(f"Help command used by {ctx.author.name}")
    
    @commands.command(name="info", help="Show information about the bot")
    async def info(self, ctx):
        """Displays information about the bot."""
        embed = discord.Embed(
            title="Bot Information",
            description="A customizable Discord bot with AI capabilities that responds to user messages.",
            color=discord.Color.blue()
        )
        
        # Add bot statistics
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Latency", value=f"{round(self.bot.latency * 1000)}ms", inline=True)
        
        # Add bot version and library info
        embed.add_field(name="Library", value=f"discord.py {discord.__version__}", inline=True)
        embed.add_field(name="Source", value="[GitHub](https://github.com/yourusername/discord-bot)", inline=True)
        
        # Add bot avatar if available
        if self.bot.user.avatar:
            embed.set_thumbnail(url=self.bot.user.avatar.url)
        
        await ctx.send(embed=embed)
        logger.debug(f"Info command used by {ctx.author.name}")
    
    @commands.command(name="echo", help="Repeat a message")
    async def echo(self, ctx, *, message=None):
        """Repeats the user's message."""
        if message:
            await ctx.send(message)
        else:
            await ctx.send("You didn't provide a message to echo!")
        logger.debug(f"Echo command used by {ctx.author.name}")
    
    @commands.command(name="serverinfo", help="Show information about the server")
    async def server_info(self, ctx):
        """Displays information about the current server."""
        guild = ctx.guild
        
        if not guild:
            await ctx.send("This command can only be used in a server.")
            return
        
        embed = discord.Embed(
            title=f"{guild.name} Info",
            description=guild.description or "No description",
            color=discord.Color.blue()
        )
        
        # Add server stats
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Member Count", value=str(guild.member_count), inline=True)
        embed.add_field(name="Channels", value=str(len(guild.channels)), inline=True)
        embed.add_field(name="Roles", value=str(len(guild.roles)), inline=True)
        embed.add_field(name="Created", value=guild.created_at.strftime("%Y-%m-%d"), inline=True)
        
        # Add server icon if available
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        
        await ctx.send(embed=embed)
        logger.debug(f"Serverinfo command used by {ctx.author.name}")

async def setup(bot):
    await bot.add_cog(BasicCommands(bot))
