import discord
from discord.ext import commands
import logging
from tokens import DiscordToken
import difflib
from translations.ua import *

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)

handler = logging.FileHandler(filename='botlogger.log', encoding='utf-8', mode='w')

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands.")
    except Exception as e:
        logger.info(f"Error syncing commands: {e}")

@bot.tree.command(name="missing_mentions", description=f"{MISSING_MENTIONS_COMMAND_DESCRIPTION}.")
@discord.app_commands.describe(
    message_link=f"{MISSING_MENTIONS_MESSAGE_LINK_DESCRIPTION}.",
    role=f"{MISSING_MENTIONS_ROLE_DESCRIPTION}."
)
@commands.has_permissions(administrator=True)
async def missing_mentions(ctx: discord.Interaction, message_link: str, role: discord.Role):
    logger.info(f"Received missing_mentions: {message_link}, {role.name}, from user: {ctx.user.name} <@{ctx.user.id}>")
    try:
        parts = message_link.split('/')
        parts = message_link.split('/')
        if (not parts or len(parts) < 7):
            await ctx.response.send_message(f"{ERROR_WRONG_URL}: {message_link}", ephemeral=True)
            return
        
        guild_id = int(parts[4])
        channel_id = int(parts[5])
        message_id = int(parts[6])
        guild = bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id)
        message = await channel.fetch_message(message_id)

        if message.author.id != 475744554910351370:
            await ctx.response.send_message(f"{ERROR_NOT_APPOLO}.", ephemeral=True)
            return
        
        event_mentions = []

        await ctx.guild.chunk()

        role_members = [member.id for member in role.members]

        if not role_members:
            await ctx.response.send_message(f"{MISSING_MENTIONS_ERROR_NO_MEMBERS}: **{role.name}**.", ephemeral=True)
            return

        for field in message.embeds[0].fields:
            if field.value[:6] != '>>> <@':
                continue
            mentions = field.value[4:].replace('<@', '').replace('>', '')
            event_mentions.extend([int(m) for m in mentions.split('\n') if m])
        
        missing_reactions_list = set(role_members) - set(event_mentions)
        if not missing_reactions_list:
            await ctx.response.send_message(f"{MISSING_MEMBERS_ALL_REACTED} {message_link}.", ephemeral=True)
            return

        missing_reactions_str = "\n".join(f"<@{reaction}>" for reaction in missing_reactions_list)
        await ctx.response.send_message(f"{message_link} {MISSING_MENTIONS_RESPONSE_SUCCESS}:\n{missing_reactions_str}")

    except Exception as e:
        await ctx.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.info(f"{ERROR_GENERIC}: {e}; args: {message_link}; {type(role)}")

@bot.command()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send(f"{SYNCED}.")

@bot.tree.command(name="missing_voice", description=f"{MISSING_VOICE_COMMAND_DESCRIPTION}.")
@discord.app_commands.describe(
    message_link=f"{MISSING_VOICE_MESSAGE_LINK_DESCRIPTION}.",
    voice_name=f"{MISSING_VOICE_CHANNEL_NAME_DESCRIPTION}."
)
async def missing_voice(ctx: discord.Interaction, message_link: str, voice_name: str):
    logger.info(f"Received missing_voice: {message_link}, {voice_name}, from user: {ctx.user.name} <@{ctx.user.id}>")
    try:
        parts = message_link.split('/')
        if (not parts or len(parts) < 7):
            await ctx.response.send_message(f"{ERROR_WRONG_URL}: {message_link}", ephemeral=True)
            return

        guild_id = int(parts[4])
        channel_id = int(parts[5])
        message_id = int(parts[6])
        guild = bot.get_guild(guild_id)
        channel = guild.get_channel(channel_id)
        message = await channel.fetch_message(message_id)

        mentioned_ids = [mention.id for mention in message.mentions]
        if not mentioned_ids:
            await ctx.response.send_message(f"{MISSING_VOICE_ERROR_NO_MEMBERS}", ephemeral=True)
            return
        
        await ctx.guild.chunk()

        voice_channel_names = [vc.name for vc in guild.voice_channels]
        matches = difflib.get_close_matches(voice_name, voice_channel_names, n=3, cutoff=0.5)
        if not matches:
            await ctx.response.send_message(f"{MISSING_VOICE_ERROR_NO_CHANNEL_MATCHES}: **{voice_name}**.", ephemeral=True)
            return
        if len(matches) > 1:
            options = "\n".join(f"- `{match}`" for match in matches)
            await ctx.response.send_message(f"{MISSING_VOICE_ERROR_MULTIPLE_MATCHES_FIRST}:\n{options}\n{MISSING_VOICE_ERROR_MULTIPLE_MATCHES_SECOND}.", ephemeral=True)
            return
        elif len(matches) == 1:
            channel_name = matches[0]
        voice_channel = discord.utils.get(guild.voice_channels, name=channel_name)
        connected_ids = [member.id for member in voice_channel.members]

        missing_members = set(mentioned_ids) - set(connected_ids)

        if not missing_members:
            await ctx.response.send_message(f"{MISSING_VOICE_ALL_PRESENT} {voice_channel.name}.", ephemeral=True)
            return
        
        missing_mentions = f"\n".join(f"<@{member}>" for member in missing_members)
        await ctx.response.send_message(f"**{voice_channel.name}** {MISSING_VOICE_RESPONSE_SUCCESS}:\n{missing_mentions}")

    except Exception as e:
        await ctx.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {message_link}; {voice_name}")

bot.run(DiscordToken, log_handler=handler, log_level=logging.INFO)