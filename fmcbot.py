import discord
import logging
from tokens import DiscordToken
from monitorlist import targets

handler = logging.FileHandler(filename='bot.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.message_content = True
intents.presences = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    print('Got message')
    
    if message.content.startswith('test'):
        print('Got message starts with hello')
        userstatuses = []
        for key, value in targets.items():
            try:
                tempstorage = await client.fetch_user(value)
                userstatuses.append(temp_storage)
            except discord.NotFound as e:
                logger.warning(f"User {key}:{value} not found, skipping.")
                continue
            except discord.HTTPException as e:
                logger.error(f"HTTPException occured: {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                continue
        print(f'Parsed userstatuses from targets list')
        print(f'userstatuses.lenght: {len(userstatuses)}')
        for value in userstatuses:
            await message.channel.send(f'entry {value.display_name}')
        print(f'Sent user names from targets list')

client.run(DiscordToken, log_handler=handler, log_level=logging.DEBUG)