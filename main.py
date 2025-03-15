import discord
from discord.ext import commands
import logging
from tokens import DiscordToken
from translations.ua import *

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)

handler = logging.FileHandler(filename='bot.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception as e:
        print(f"Error syncing commands: {e}")

@bot.tree.command(name="missing_mentions", description=f"{COMMAND_DESCRIPTION}.")
@discord.app_commands.describe(
    message_link=f"{MESSAGE_LINK_DESCRIPTION}.",
    role=f"{ROLE_DESCRIPTION}."
)
@commands.has_permissions(administrator=True)
async def missing_mentions(ctx: discord.Interaction, message_link: str, role: discord.Role):
    print(f"Received missing_mentions: {message_link}, {role.name}")
    try:
        parts = message_link.split('/')
        guild_id = int(parts[4])
        channel_id = int(parts[5])
        message_id = int(parts[6])
        guild = bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id)
        message = await channel.fetch_message(message_id)

        if message.author.id != 475744554910351370:
            await ctx.response.send_message(f"{ERROR_NOT_APPOLO}.")
            return
        
        event_mentions = []

        await ctx.guild.chunk()

        role_members = [member.id for member in role.members]

        if not role_members:
            await ctx.response.send_message(f"{ERROR_NO_MEMBERS}.")
            return

        for field in message.embeds[0].fields:
            if field.value[:6] != '>>> <@':
                continue
            mentions = field.value[4:].replace('<@', '').replace('>', '')
            event_mentions.extend([int(m) for m in mentions.split('\n') if m])
        
        missing_reactions_list = set(role_members) - set(event_mentions)
        missing_reactions_str = ""
        for reaction in missing_reactions_list:
            missing_reactions_str = f"{missing_reactions_str}<@{reaction}>\n"

        await ctx.response.send_message(f"{message_link} {RESPONSE_SUCCESS}:\n{missing_reactions_str}")

    except Exception as e:
        await ctx.response.send_message(f"{ERROR_GENERIC}: {e}")

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send(f"{SYNCED}.")

bot.run(DiscordToken, log_handler=handler, log_level=logging.WARNING)