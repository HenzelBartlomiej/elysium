import discord
import os

from discord.ext import commands

TOKEN = os.environ.get("BOT_TOKEN")
CHANNEL_ID = 1107241494110289980

bot = commands.Bot(command_prefix="!", intents=discord.Intents.all())

@bot.event
async def on_message(message):  # When a message is sent
    if (message.author.bot == False):  # If the message is not from a bot
        if 'airdrop' in message.content:
            channel = message.channel.name
            await message.reply("""
            We have no plans for airdrop\n
Check our docs: https://docs.elysium-chain.com/en/ \n
            """)
            restricted_channels = ["bot-commands"] # List of restricted channels
        if 'testnet' in message.content:
            channel = message.channel.name
            await message.reply("""
            There are no plans for testnet at the moment\n
check our roadmap: https://docs.elysium-chain.com/en/introduction/roadmap \n
check our docs: https://docs.elysium-chain.com/en/ \n
            """)
            restricted_channels = ["bot-commands"] # List of restricted channels


@bot.event
async def on_ready():
    print("Bot is online")
    channel = bot.get_channel(CHANNEL_ID)
    await channel.send("Hello my master, your bot is here")


bot.run(BOT_TOKEN)