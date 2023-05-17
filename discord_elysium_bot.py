import discord
import os

from discord.ext import commands

BOT_TOKEN = os.environ.get("BOT_TOKEN")


bot = commands.Bot(command_prefix="!", intents=discord.Intents(messages=True, message_content=True))


phrases = [
([("When","Wen"), ("binance","ZNULLLLZ")], """Hi, {}! This is a long-term project. And you are very early! \nListing on Binance is not a main target, since it is really centralized. \nFollow Elysium's Twitter and stay tuned! -> <https://twitter.com/Elysium_chain>"""),
([("Answer","Hard"), ("Zealy","Crew","quest","task")], """Hi, {}! \nZealy quests are the main way to get Pioneers Program keys. \nMost of the quests are hard, but it is an additional source of XP. \nThe main one are Team Boosts. Read more here -> <https://zealy.io/c/elysium/questboard/4ff7d357-5a67-4738-8863-32033104f845>"""),
([("Give", "share", "send", "get" ), ("Answer","ZNULLLLZ")], """Hi, {}! \nSharing answers is forbidden, it may lead to a ban. \nMost of the quests are hard, but it is an additional source of XP. \nThe main one are Team Boosts. Read more here -> <https://zealy.io/c/elysium/questboard/4ff7d357-5a67-4738-8863-32033104f845>"""),
([("Is", "There", "Where", "When", "Wen"), ("Airdrop","ZNULLLLZ")], """Hi, {}! \nThis is a long term project. And you are very early! \nYou can check Elysium's testnet launch roadmap here -> <https://docs.elysium-chain.com/en/introduction/roadmap>"""),
([("How are you","ZNULLLLZ"),("you","ZNULLLLZ")], """Hi, {}! \nGlad you asked, I am great! What about you?"""),
([("GCH","ZNULLLLZ"), ("code","ZNULLLLZ")], """Hi, {}! \nSorry, but I can only say that it is hidden in a plain sight. \nGood luck!"""),
([("good","great", "glad"), ("here","ZNULLLLZ")], """Hi, {}! \nGreat that you like it here :) \nYou should study Elysium documentation -> <https://docs.elysium-chain.com/en/> \nGood luck!"""),
([("any","ZNULLLLZ"), ("update","news")], """Hi, {}! \nYou can check news and updates about Elysium in our Twitter! \nDon't forget to follow! -> <https://twitter.com/Elysium_chain>"""),
([("What", "is"), ("Elysium","ZNULLLLZ")], """Hi, {}! \nElysium is an L1 blockchain designed from the ground up to solve the current problems faced by existing blockchains.  \nWe have reimagined every aspect of the technology, from tokenomics to consensus, to create a fundamentally new distributed system. \nYou can get more information here -> <https://docs.elysium-chain.com/en/>"""),
([("What", "project"), ("about","ZNULLLLZ")], """Hi, {}! \nElysium is an L1 blockchain designed from the ground up to solve the current problems faced by existing blockchains.  \nWe have reimagined every aspect of the technology, from tokenomics to consensus, to create a fundamentally new distributed system. \nYou can get more information here -> <https://docs.elysium-chain.com/en/>"""),
([("How","ZNULLLLZ"), ("keys","ZNULLLLZ")], """Hi, {}! \nIn order to obtain keys you should complete Zealy tasks -> <https://zealy.io/c/elysium/questboard> \nKeys' whitelists and at levels 10/12/14/16 \nThere are still many to claim!"""),
([("How","ZNULLLLZ"), ("WL","whitelist")], """Hi, {}! \nTo get whitelisted you need to complete Zealy quests -> <https://zealy.io/c/elysium/questboard> \nIt takes some time, but be patient!"""),
([("How","ZNULLLLZ"), ("role","ZNULLLLZ")], """Hi, {}! \nThe only way is Zealy quests. \nHere is the link -> <https://zealy.io/c/elysium/questboard>"""),
]


phrases2 = [
([("When","Wen"), ("testnet","ZNULLLLZ"), ("launch","ZNULLLLZ")], """Hi, {}! This is a long-term project. And you are very early! \nYou can check Elysium's testnet launch roadmap here -> <https://docs.elysium-chain.com/en/introduction/roadmap>"""),
([("When","Wen"), ("mainnet","ZNULLLLZ"), ("launch","ZNULLLLZ")], """Hi, {}! This is a long-term project. And you are very early! \nYou can check Elysium's mainnet launch roadmap here -> <https://docs.elysium-chain.com/en/introduction/roadmap>"""),
([("How","get"), ("team","ZNULLLLZ"), ("boost","ZNULLLLZ")], """Hi, {}! Chat on our server: we take into account among others, a number of meaningful words, engaging with other users, showing up along the day, etc \nCreate different quality content such as videos, memes, images, articles… (this will provide more XP)"""),
]


phrases3 = [
([("When","Wen"), ("launch","ZNULLLLZ"), ("testnet","mainnet")  ], """Hi, {}! This is a long-term project. And you are very early! \nCheck Elysium's roadmap here -> <https://docs.elysium-chain.com/en/introduction/roadmap>"""),
([("When","Wen"), ("testnet","ZNULLLLZ"), ("launch","ZNULLLLZ") ], """Hi, {}! This is a long-term project. And you are very early! \nYou can check Elysium's testnet launch roadmap here -> <https://docs.elysium-chain.com/en/introduction/roadmap>"""),
([("When","Wen"), ("mainnet","ZNULLLLZ"), ("launch","ZNULLLLZ") ], """Hi, {}! This is a long-term project. And you are very early! \nYou can check Elysium's mainnet launch roadmap here -> <https://docs.elysium-chain.com/en/introduction/roadmap>"""),
]


@bot.event
async def on_message(message):
    if (message.author.bot == False): 
        for phrase in phrases:
          if (any ((x.lower() in message.content.lower()) for x in phrase[0][0])) and (any ((x.lower() in message.content.lower()) for x in phrase[0][1])): 
                # print(phrase[1])
                # channel = message.channel.name
                user_name = message.author.name
                await message.reply(f"{phrase[1]}".format(user_name))
        for phrase in phrases2:
          if (any ((x.lower() in message.content.lower()) for x in phrase[0][0])) and (any((x.lower() in message.content.lower()) for x in phrase[0][1])) and (any((x.lower() in message.content.lower()) for x in phrase[0][2])): 
                # print(phrase[1])
                # channel = message.channel.name
                user_name = message.author.name
                await message.reply(f"{phrase[1]}".format(user_name))
        for phrase in phrases3:
          if (any ((x.lower() in message.content.lower()) for x in phrase[0][0])) and (any((x.lower() in message.content.lower()) for x in phrase[0][1])) and not (any((x.lower() in message.content.lower()) for x in phrase[0][2])): 
                # print(phrase[1])
                # channel = message.channel.name
                user_name = message.author.name
                await message.reply(f"{phrase[1]}".format(user_name))


bot.run(BOT_TOKEN)