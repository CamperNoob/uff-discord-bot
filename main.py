import discord
import asyncio
import random
import logging
import os
import pymysql.cursors
import difflib
import traceback
import pymysql
import re
import requests
from discord.ext import commands, tasks
from logging.handlers import TimedRotatingFileHandler
from collections import defaultdict
from datetime import datetime, time, timedelta
from configs.tokens import DiscordToken, MySQL, Grafana, Servers
from configs.tokens import ApolloID as apollo_id
from configs.seeding_messages_config import autopost_conf
from configs.perms import unpack_conf, unpack_matching_conf, unpack_matching
from translations.ua import *
import csv
import io

DISCORD_MAX_MESSAGE_LEN = 2000

logger = logging.getLogger("discord")
logger.setLevel(logging.INFO)

os.makedirs("logs", exist_ok=True)

# handler = logging.FileHandler(filename='botlogger.log', encoding='utf-8', mode='w')
handler = TimedRotatingFileHandler(
    filename='logs/botlogger.log',
    when="midnight",
    interval=1,
    backupCount=10,
    encoding='utf-8',
    utc=True
)

intents = discord.Intents.default()
intents.messages = True
intents.message_content = True
intents.guilds = True
intents.members = True

autopost_enabled = autopost_conf.get("enabled", False)

message_pool = []

bot = commands.Bot(command_prefix="/", intents=intents)

def seconds_until(target_time):
    now = datetime.now()
    target = datetime.combine(now.date(), target_time)
    if now > target:
        target += timedelta(days=1)
    return (target - now).total_seconds()

def get_db_connection():
    return pymysql.connect(
        host=MySQL.get("host"),
        port=MySQL.get("port", 3306),
        user=MySQL.get("user"),
        password=MySQL.get("password"),
        database=MySQL.get("database"),
        cursorclass=pymysql.cursors.DictCursor
    )

class missingVoiceChannelSelectView(discord.ui.View):
    def __init__(self, matches, voice_channel_names, ctx, message_link):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.result = None
        self.message_link = message_link
        for channel in matches:
            channel_name = voice_channel_names[channel]
            self.add_item(missingVoiceChannelButton(label=channel_name))
        self.add_item(missingVoiceCancelButton())
    async def on_timeout(self):
        await self.ctx.edit_original_response(content=f"{MISSING_VOICE_TIMEOUT}.", view=None)

class missingVoiceChannelButton(discord.ui.Button):
    def __init__(self, label):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
    async def callback(self, interaction: discord.Interaction):
        self.view.result = self.label
        await interaction.response.edit_message(content=f"{MISSING_VOICE_SELECTED_CHANNEL}: **{self.label}**", view=None)
        self.view.stop()
        await missing_voice_handler(interaction, self.label, self.view.message_link)

class missingVoiceCancelButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label=f"{MISSING_VOICE_CANCEL_LABEL}", style=discord.ButtonStyle.danger)
    async def callback(self, interaction: discord.Interaction):
        self.view.result = None
        await interaction.response.edit_message(content=f"{MISSING_VOICE_CANCEL_MULTIPLE_SELECT}.", view=None)
        self._view.stop()

async def missing_voice_handler(ctx: discord.Interaction, channel_name: str, message_link: str):
    try:
        guild = ctx.guild
        voice_channel = discord.utils.get(guild.voice_channels, name=channel_name)
        if not voice_channel:
            await ctx.followup.send(f"{MISSING_VOICE_ERROR_NO_CHANNEL_MATCHES}: **{channel_name}**.", ephemeral=True)
            return
        connected_ids = [member.id for member in voice_channel.members]
        message = await fetch_message_from_url(ctx, message_link)
        if not message:
            return
        mentioned_ids = [mention.id for mention in message.mentions]
        if not mentioned_ids:
            await ctx.followup.send(f"{MISSING_VOICE_ERROR_NO_MEMBERS}: {message_link}", ephemeral=True)
            return
        missing_members = set(mentioned_ids) - set(connected_ids)
        if not missing_members:
            await ctx.followup.send(f"{MISSING_VOICE_ALL_PRESENT} {voice_channel.name}.", ephemeral=True)
            return
        missing_mentions = "\n".join(f"<@{member}>" for member in missing_members)
        await ctx.followup.send(f"**{voice_channel.name}** {MISSING_VOICE_RESPONSE_SUCCESS}:\n{missing_mentions}", ephemeral=False)
    except Exception as e:
        await ctx.followup.send(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}")

async def fetch_message_from_url(ctx: discord.Interaction, message_link):
    try:
        if not message_link:
            raise ValueError("Message link is missing")
        parts = message_link.split('/')
        if (not parts or len(parts) < 7):
                await ctx.response.send_message(f"{ERROR_WRONG_URL}: {message_link}", ephemeral=True)
                return
        #guild_id = int(parts[4])
        channel_id = int(parts[5])
        message_id = int(parts[6])
        guild = ctx.guild
        channel = guild.get_channel(channel_id)
        if channel is None:
            await ctx.response.send_message(f"{ERROR_MESSAGE_NOT_FOUND}: {message_link}", ephemeral=True)
            return None
        message = await channel.fetch_message(message_id)
        return message
    except discord.NotFound:
        try:
            await ctx.followup.send(f"{ERROR_MESSAGE_NOT_FOUND}: {message_link}", ephemeral=True)
        except Exception as ee:
            logger.error(f"{ERROR_GENERIC}: {ee}; traceback: {traceback.format_exc()}")
        return None
    except discord.Forbidden:
        try:
            await ctx.followup.send(f"{ERROR_NO_PERMISSION} **{channel.name}**.", ephemeral=True)
        except Exception as ee:
            logger.error(f"{ERROR_GENERIC}: {ee}; traceback: {traceback.format_exc()}")
        return None
    except Exception as e:
        try:
            await ctx.followup.send(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        except Exception as ee:
            logger.error(f"{ERROR_GENERIC}: {ee}; traceback: {traceback.format_exc()}")
        logger.error(f"{ERROR_GENERIC}: {e}; traceback: {traceback.format_exc()}")
        return None

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} commands.")
    except Exception as e:
        logger.error(f"Error syncing commands: {e}")
    try:
        if autopost_enabled:
            if not daily_autopost.is_running():
                await before_daily_autopost()
                daily_autopost.start()
    except Exception as e:
        logger.error(f"[daily_autopost():on_ready()] {ERROR_GENERIC}: {e}; traceback: {traceback.format_exc()}")

@tasks.loop(hours=24)
async def daily_autopost():
    global message_pool
    try:
        target = await bot.fetch_channel(autopost_conf.get("target_id"))
        if not message_pool:
            message_pool = autopost_conf.get("messages").copy()
        message = random.choice(message_pool)
        message_pool.remove(message)
        await target.send(message)
        logger.info(f"[daily_autopost()] Sent the post with message: {message}.")
    except Exception as e:
        logger.error(f"[daily_autopost()] {ERROR_GENERIC}: {e}; traceback: {traceback.format_exc()}")

async def before_daily_autopost():
    try:
        target_time = time(hour=autopost_conf.get("hour", 9), minute=autopost_conf.get("minute", 15))
        wait_time = seconds_until(target_time)
        logger.info(f"[daily_autopost():before_daily_autopost()] Waiting {wait_time:.0f} seconds until first autopost.")
        await asyncio.sleep(wait_time)
    except Exception as e:
        logger.error(f"[daily_autopost():before_daily_autopost()] {ERROR_GENERIC}: {e}; traceback: {traceback.format_exc()}")

@bot.tree.command(name="missing_mentions", description=f"{MISSING_MENTIONS_COMMAND_DESCRIPTION}.")
@discord.app_commands.describe(
    role=f"{MISSING_MENTIONS_ROLE_DESCRIPTION}.",
    message_link=f"{MISSING_MENTIONS_MESSAGE_LINK_DESCRIPTION}.",
    role2=f"{MISSING_MENTIONS_ADDITIONAL_ROLE_DESCRIPTION} {MISSING_MENTIONS_ROLE_DESCRIPTION}.",
    role3=f"{MISSING_MENTIONS_ADDITIONAL_ROLE_DESCRIPTION} {MISSING_MENTIONS_ROLE_DESCRIPTION}.",
)
@commands.has_any_role(*unpack_conf())
async def missing_mentions(ctx: discord.Interaction, role: discord.Role, message_link: str = None, role2: discord.Role = None, role3: discord.Role = None):
    logger.info(f"Received missing_mentions: {message_link}, {[role.name, role2.name if role2 else None, role3.name if role3 else None]}, from user: {ctx.user.name} <@{ctx.user.id}>")
    try:
        if not message_link:
            async for message in ctx.channel.history(limit=None, oldest_first=True):
                if message.author.id == apollo_id:
                    message_link = f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}/{message.id}"
                    break
            if not message_link:
                await ctx.response.send_message(f"{ERROR_MESSAGE_LINK_CANNOT_BE_RESOLVED} {MISSING_MENTIONS_CANNOT_FIND_APOLLO_MESSAGE}.", ephemeral=True)
                return
        message = await fetch_message_from_url(ctx, message_link)
        if not message:
            return
        if message.author.id != apollo_id:
            await ctx.response.send_message(f"{ERROR_NOT_APPOLO}: {message_link}", ephemeral=True)
            return
        event_mentions = []
        await ctx.guild.chunk()
        role_members = set(member.id for member in role.members)
        if role2:
            role_members |= set(member.id for member in role2.members)
        if role3:
            role_members |= set(member.id for member in role3.members)
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
            await ctx.response.send_message(f"{MISSING_MENTIONS_MEMBERS_ALL_REACTED} {message_link}.", ephemeral=True)
            return
        missing_reactions_str = "\n".join(f"<@{reaction}>" for reaction in missing_reactions_list)
        await ctx.response.send_message(f"{message_link} {MISSING_MENTIONS_RESPONSE_SUCCESS}:\n{missing_reactions_str}")
    except Exception as e:
        await ctx.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {message_link}; {type(role)}; {type(role2)}; {type(role3)}; traceback: {traceback.format_exc()}")

@bot.command()
async def sync(ctx):
    logger.info("Got SYNC request.")
    await bot.tree.sync()
    await ctx.send(f"{SYNCED}.")
    logger.info("SYNC success.")

@bot.tree.command(name="missing_voice", description=f"{MISSING_VOICE_COMMAND_DESCRIPTION}.")
@discord.app_commands.describe(
    voice_name=f"{MISSING_VOICE_CHANNEL_NAME_DESCRIPTION}.",
    message_link=f"{MISSING_VOICE_MESSAGE_LINK_DESCRIPTION}."
    
)
async def missing_voice(ctx: discord.Interaction,  voice_name: str, message_link: str = None):
    logger.info(f"Received missing_voice: {voice_name}, {message_link}, from user: {ctx.user.name} <@{ctx.user.id}>")
    try:
        if not message_link:
            async for message in ctx.channel.history(limit=None, oldest_first=True):
                if message.content.startswith("~"):
                    message_link = f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}/{message.id}"
                    break
            if not message_link:
                await ctx.response.send_message(f"{ERROR_MESSAGE_LINK_CANNOT_BE_RESOLVED} {MISSING_VOICE_CANNOT_FIND_MESSAGE}.", ephemeral=True)
                return
        await ctx.guild.chunk()
        voice_channel_names = {vc.name.lower().replace(' ', '_'):vc.name for vc in ctx.guild.voice_channels}
        matches = difflib.get_close_matches(voice_name.lower().replace(' ', '_'), voice_channel_names.keys(), n=3, cutoff=0.5)
        if not matches:
            await ctx.response.send_message(f"{MISSING_VOICE_ERROR_NO_CHANNEL_MATCHES}: **{voice_name}**.", ephemeral=True)
            return
        if len(matches) > 1:
            view = missingVoiceChannelSelectView(matches, voice_channel_names, ctx, message_link)
            await ctx.response.send_message(f"{MISSING_VOICE_MULTIPLE_MATCHES_FIRST}\n{MISSING_VOICE_MULTIPLE_MATCHES_SECOND}:", view=view, ephemeral=True)
            await view.wait()
            if view.result is None:
                await ctx.edit_original_response(content=f"{MISSING_VOICE_CANCEL_MULTIPLE_SELECT}.", view=None, ephemeral=True)
                return
            return #await missing_voice_handler(ctx, view.result, message_link)
        if len(matches) == 1:
            channel_name = voice_channel_names[matches[0]]
            await ctx.response.send_message(f"{MISSING_VOICE_EXACT_MATCH_CHANNEL}: **{channel_name}**", ephemeral=True)
            await missing_voice_handler(ctx, channel_name, message_link)
    except Exception as e:
        await ctx.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {message_link}; {voice_name}; traceback: {traceback.format_exc()}")

@bot.tree.command(name="generate_roster", description=f"{GENERATE_ROSTER_COMMAND_DESCRIPTION}.")
@discord.app_commands.describe(
    message_link=f"{GENERATE_ROSTER_PARAMETER_DESCRIPTION}."
    
)
@commands.has_any_role(*unpack_conf())
async def generate_roster(ctx: discord.Interaction, message_link: str):
    guild = ctx.guild
    emoji_map = {
        'sl':discord.utils.get(bot.emojis, name='role_sl') or 'SL',
        'engi':discord.utils.get(bot.emojis, name='role_engi') or 'Engineer',
        'rifl':discord.utils.get(bot.emojis, name='role_rifleman') or 'Rifleman',
        'rifleman':discord.utils.get(bot.emojis, name='role_rifleman') or 'Rifleman',
        'pilot':discord.utils.get(bot.emojis, name='role_pilot') or 'Pilot',
        'mortar':discord.utils.get(bot.emojis, name='role_mortar') or 'Mortar',
        'mg':discord.utils.get(bot.emojis, name='role_mg') or 'MG',
        'hmg':discord.utils.get(bot.emojis, name='role_mg') or 'MG',
        'medic':discord.utils.get(bot.emojis, name='role_medic') or 'Medic',
        'med':discord.utils.get(bot.emojis, name='role_medic') or 'Medic',
        'sniper':discord.utils.get(bot.emojis, name='role_marksman') or 'Marksman',
        'marksman':discord.utils.get(bot.emojis, name='role_marksman') or 'Marksman',
        'lat':discord.utils.get(bot.emojis, name='role_lat') or 'LAT',
        'hat':discord.utils.get(bot.emojis, name='role_hat') or 'HAT',
        'gp':discord.utils.get(bot.emojis, name='role_gp') or 'GP',
        'sap':discord.utils.get(bot.emojis, name='role_sapper') or 'Sapper',
        'sapper':discord.utils.get(bot.emojis, name='role_sapper') or 'Sapper',
        'crewman':discord.utils.get(bot.emojis, name='role_crewman') or 'Crewman',
        'crew':discord.utils.get(bot.emojis, name='role_crewman') or 'Crewman',
        'cr':discord.utils.get(bot.emojis, name='role_crewman') or 'Crewman',
        'autorifl':discord.utils.get(bot.emojis, name='role_autorifleman') or 'Automatic Rifleman',
        'autorifleman':discord.utils.get(bot.emojis, name='role_autorifleman') or 'Automatic Rifleman',
        'scout':discord.utils.get(bot.emojis, name='role_scout') or 'Scout',
        'ifv':discord.utils.get(bot.emojis, name='map_wheelifv') or 'IFV',
        'tank':discord.utils.get(bot.emojis, name='map_tank') or 'Tank',
        'truck':discord.utils.get(bot.emojis, name='map_truck') or 'Truck',
        'peh':discord.utils.get(bot.emojis, name='map_truck') or 'Truck',
        'logi':discord.utils.get(bot.emojis, name='map_logitruck') or 'Logi',
        'rws':discord.utils.get(bot.emojis, name='map_jeeprws') or 'RWS',
        'mrap':discord.utils.get(bot.emojis, name='map_jeep') or 'MRAP',
        'heli':discord.utils.get(bot.emojis, name='map_heli') or 'Helicopter',
        'helicopter':discord.utils.get(bot.emojis, name='map_heli') or 'Helicopter',
        'boat':discord.utils.get(bot.emojis, name='map_boat') or 'Boat',
        'orange':'🟧',
        'оранж':'🟧',
        'оранжевий':'🟧',
        'black':'⬛',
        'чорний':'⬛',
        'brown':'🟫',
        'коричневий':'🟫',
        'purp':'🟪',
        'purple':'🟪',
        'фіолетовий':'🟪',
        'red':'🟥',
        'червоний':'🟥',
        'черв':'🟥',
        'white':'⬜',
        'білий':'⬜',
        'blue':'🟦',
        'синій':'🟦',
        'голубий':'🟦',
        'блакитний':'🟦',
        'green':'🟩',
        'зелений':'🟩',
        'зел':'🟩',
        'yellow':'🟨',
        'жовтий':'🟨'
    }
    try:
        await guild.chunk()
        message = await fetch_message_from_url(ctx, message_link)
        guild_discord_members = guild.members
        guild_members = {member.name.lower():member.id for member in guild_discord_members if member.name is not None}
        guild_members_display_names = defaultdict(list)
        for member in guild_discord_members:
            guild_members_display_names[member.display_name.lower()].append(member.id)
        roster_string_list = message.content.split('\n')
        return_text = []
        for line in roster_string_list:
            if not line:
                continue
            linesplit = line.split(';')
            line_list = []
            for item in linesplit:
                if item.startswith('@'):
                    member_id = guild_members.get(item[1:].lower())
                    if member_id:
                        line_list.append(f"<@{member_id}> ")
                    else:
                        matches = guild_members_display_names.get(item[1:].lower())
                        if not matches:
                            line_list.append(f"{item} ")
                        elif len(matches) == 1:
                            line_list.append(f"<@{matches[0]}> ")
                        else:
                            multiple_matches = "|".join([f'<@{id}>' for id in matches])
                            line_list.append(f"{multiple_matches} ")    
                elif item.startswith('<@') and item.endswith('>'):
                    line_list.append(f"{item} ")
                elif item.startswith('~'):
                    color_value = emoji_map.get(item[1:].lower())
                    if color_value:
                        line_list.append(f"\n**{item[1:]}** {color_value} ")
                    elif not item[1:] or item[1:] == ' ':
                        line_list.append(f" ")
                    else:
                        line_list.append(f"**{item[1:]}** ")
                else:
                    value_str = emoji_map.get(item.lower())
                    if value_str:
                        line_list.append(f"{value_str} ")
                    else:
                        line_list.append(f"{item} ")
            return_text.append(" ".join(line_list))
        if return_text:
            message_text = f"{GENERATE_ROSTER_SUCCESS}:\n{'\n'.join(return_text)}"
            if len(message_text) > DISCORD_MAX_MESSAGE_LEN:
                await ctx.response.send_message(f"{message_text[:DISCORD_MAX_MESSAGE_LEN-3]}...")
            else:  
                await ctx.response.send_message(message_text)
        else:
            await ctx.response.send_message(f"{GENERATE_ROSTER_FAILED}:{message_link}")
        return
    except Exception as e:
        await ctx.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {message_link}; traceback: {traceback.format_exc()}")

@bot.tree.command(name="ping_tentative", description=f"{PING_TENTATIVE_COMMAND_DESCRIPTION}.")
@discord.app_commands.describe(
    message_link=f"{MISSING_MENTIONS_MESSAGE_LINK_DESCRIPTION}."
)
@commands.has_any_role(*unpack_conf())
async def ping_tentative(ctx: discord.Interaction, message_link: str = None):
    logger.info(f"Received ping_tentative: {message_link}, from user: {ctx.user.name} <@{ctx.user.id}>")
    try:
        if not message_link:
            async for message in ctx.channel.history(limit=None, oldest_first=True):
                if message.author.id == apollo_id:
                    message_link = f"https://discord.com/channels/{ctx.guild.id}/{ctx.channel.id}/{message.id}"
                    break
            if not message_link:
                await ctx.response.send_message(f"{ERROR_MESSAGE_LINK_CANNOT_BE_RESOLVED} {MISSING_MENTIONS_CANNOT_FIND_APOLLO_MESSAGE}.", ephemeral=True)
                return
        message = await fetch_message_from_url(ctx, message_link)
        if not message:
            return
        if message.author.id != apollo_id:
            await ctx.response.send_message(f"{ERROR_NOT_APPOLO}: {message_link}", ephemeral=True)
            return
        event_mentions = []
        for field in message.embeds[0].fields:
            if field.name[:11] == '<:tentative' and field.value[:6] == '>>> <@':
                mentions = field.value[4:].replace('<@', '').replace('>', '')
                event_mentions.extend([int(m) for m in mentions.split('\n') if m])
        if not event_mentions:
            await ctx.response.send_message(f"{PING_TENTATIVE_MENTIONS_MEMBERS_ALL_REACTED} {message_link}.", ephemeral=True)
            return
        ping_tentative_str = "\n".join(f"<@{reaction}>" for reaction in event_mentions)
        await ctx.response.send_message(f"{PING_TENTATIVE_RESPONSE_SUCCESS}:\n{ping_tentative_str}")
    except Exception as e:
        await ctx.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {message_link}; traceback: {traceback.format_exc()}")

@bot.tree.command(name="grafana_ignore", description=f"{GRAFANA_IGNORE_COMMAND_DESCRIPTION}.")
@discord.app_commands.describe(
    ignore=f"{GRAFANA_IGNORE_IGNORE_VARIABLE}.",
    player_id=f"{GRAFANA_IGNORE_PLAYER_ID_VARIABLE}.",
    name=f"{GRAFANA_IGNORE_NAME_VARIABLE}.",
    steam_id=f"{GRAFANA_IGNORE_STEAM_ID_VARIABLE}."
)
@discord.app_commands.choices(
    ignore=[
        discord.app_commands.Choice(name=f"{GRAFANA_IGNORE_VALUE_IGNORE}", value=1),
        discord.app_commands.Choice(name=f"{GRAFANA_IGNORE_VALUE_UNIGNORE}", value=0)
    ]
)
@commands.has_any_role(*unpack_conf())
async def grafana_ignore(interaction: discord.Interaction, ignore: int, player_id: int = None, name:str = None, steam_id: str = None):
    logger.info(f"Received grafana_ignore: {[ignore, player_id, name, steam_id]}, from user: {interaction.user.name} <@{interaction.user.id}>")
    try:
        conn = get_db_connection()
    except Exception as e:
        await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
        logger.error(f"Connection failed to db; Exception: {e}; traceback: {traceback.format_exc()}")
        return
    try:
        with conn.cursor() as cursor:
            if player_id is None:
                if not (name or steam_id):
                    await interaction.response.send_message(f"{GRAFANA_IGNORE_NEED_ID_OR_NAME}.", ephemeral=True)
                    return
                elif name and not steam_id:
                    if re.search(r"([`'\";]|--{2,})", name):
                        await interaction.response.send_message(f"{GRAFANA_IGNORE_SQL_INJECT_PROTECTION}: {name}", ephemeral=True)
                        logger.warning(f"Catched SQL inject attempt: {name}. Discord user ID: {interaction.user.id if interaction.user.id else None}")
                        return
                    try:
                        cursor.execute("SELECT id, lastName, steamID FROM dblog_players WHERE lastName LIKE %s", ('%' + name + '%',))
                        results = cursor.fetchall()
                    except Exception as e:
                        await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                        logger.error(f"Select query failed for name: {name}; Exception: {e}; traceback: {traceback.format_exc()}")
                        return
                    if not results:
                        await interaction.response.send_message(f"{GRAFANA_IGNORE_NAME_SEARCH_NO_RESULTS}: {name}", ephemeral=True)
                        return
                    elif len(results) == 1:
                        player_id = results[0]['id']
                    else:
                        message = f"{GRAFANA_IGNORE_MULTIPLE_IDS_FROM_NAME}:"
                        for r in results:
                            message += f"\n### {GRAFANA_IGNORE_NAME_STR}: `{r['lastName']}`:\n- {GRAFANA_INGORE_ID_STR}: `{r['id']}`\n- {GRAFANA_IGNORE_STEAMID_STR}: `{r['steamID']}`"
                        if len(message) > DISCORD_MAX_MESSAGE_LEN:
                            message = f"{message[:DISCORD_MAX_MESSAGE_LEN-3]}..."
                        await interaction.response.send_message(message, ephemeral=True)
                        return
                else:
                    try:
                        cursor.execute("SELECT id, lastName, steamID FROM dblog_players WHERE steamID = %s", (steam_id,))
                        results = cursor.fetchall()
                    except Exception as e:
                        await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                        logger.error(f"Select query failed for steamID: {steam_id}; Exception: {e}; traceback: {traceback.format_exc()}")
                        return
                    if not results:
                        await interaction.response.send_message(f"{GRAFANA_IGNORE_STEAMID_SEARCH_NO_RESULTS}: {steam_id}", ephemeral=True)
                        return
                    elif len(results) == 1:
                        player_id = results[0]['id']
                    else:
                        await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                        logger.warning(f"Select query for steamID: {steam_id} returned multiple results")
                        return
            try:
                cursor.execute("SELECT id FROM dblog_players WHERE id = %s", (player_id,))
                existing = cursor.fetchone()
            except Exception as e:
                await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                logger.error(f"Select query failed for id: {player_id}; Exception: {e}; traceback: {traceback.format_exc()}")
                return
            if not existing:
                await interaction.response.send_message(f"{GRAFANA_IGNORE_NO_ID_FOUND}: {player_id}", ephemeral=True)
                return
            ignore_value = ignore #1 if ignore else 0
            try:
                cursor.execute("UPDATE dblog_players SET `ignore` = %s WHERE id = %s", (ignore_value, player_id))
                conn.commit()
                cursor.execute("SELECT id, lastName, steamID, `ignore` FROM dblog_players WHERE id = %s", (player_id,))
                updated = cursor.fetchone()
                updated_ignore = GRAFANA_IGNORE_IGNORED if updated['ignore'] == 1 else GRAFANA_IGNORE_UNIGNORED
            except Exception as e:
                await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                logger.error(f"Select query failed for id: {player_id}; Exception: {e}; traceback: {traceback.format_exc()}")
                return
            await interaction.response.send_message(
                    f"### {GRAFANA_IGNORE_SUCCESS}:\n- {GRAFANA_INGORE_ID_STR}: `{updated['id']}`,\n- {GRAFANA_IGNORE_NAME_STR}: `{updated['lastName']}`,\n- {GRAFANA_IGNORE_STEAMID_STR}: `{updated['steamID']}`,\n- {GRAFANA_IGNORE_STATUS_STR}: `{updated_ignore}`.",
                    ephemeral=False
                )
    except Exception as e:
        await interaction.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {ignore}, {player_id}, {name}, {steam_id}; traceback: {traceback.format_exc()}")
    finally:
        conn.close()

@bot.tree.command(name="grafana_invite", description=f"{GRAFANA_INVITE_COMMAND_DESCRIPTION}.")
@discord.app_commands.describe(
    name=f"{GRAFANA_INVITE_NAME_VARIABLE}.",
    email=f"{GRAFANA_INVITE_EMAIL_VARIABLE}."
)
@commands.has_any_role(*unpack_conf())
async def grafana_invite(interaction: discord.Interaction, name:str, email:str = None):
    logger.info(f"Received grafana_invite: {name}, from user: {interaction.user.name} <@{interaction.user.id}>")

    def check_invites(data:list, name:str) -> tuple[bool, str]:
        exists = False
        url = None
        for invite in data:
            if invite.get('name') == name:
                exists = True
                url = invite.get('url')
                break
        return exists, url
    
    invites_endpoint = f"{Grafana.get("url")}api/org/invites"
    token = Grafana.get("token")
    header = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # check email
    def is_valid_email(email: str) -> bool:
        pattern = r'^[^@\s]+@[^@\s]+\.[^@\s]+$'
        return re.match(pattern, email) is not None
    email = email if is_valid_email(email) else None

    data = {
        "email": f"{email}",
        "loginOrEmail": email if email else name,
        "name": name,
        "role": "Viewer",
        "sendEmail": True if email else False,
    }
    try:
        try:
            response_get_noduplicates = requests.get(invites_endpoint, headers=header)
        except Exception as e:
                await interaction.response.send_message(f"{GRAFANA_INVITE_GENERIC_HTTP_FAIL}", ephemeral=True)
                logger.error(f"HTTP request failed on invite url retrieval; Exception: {e}; traceback: {traceback.format_exc()}")
                return
        if response_get_noduplicates.status_code == 200:
            exists, url = check_invites(response_get_noduplicates.json(), name)
        else:
            await interaction.response.send_message(f"{GRAFANA_INVITE_GENERIC_HTTP_FAIL}", ephemeral=True)
            logger.error(f"Did not receive proper response for get invites for duplicates. Status: {response_get.status_code}, Text: {response_get.text}")
            return
        if exists:
            await interaction.response.send_message(f"{GRAFANA_INVITE_SUCCESS}: ```{url}```", ephemeral=True)
            logger.info(f"Retrieved existing invite for user: {name}, url: {url}")
            return
        else:
            try:
                response_post = requests.post(invites_endpoint, json=data, headers=header)
            except Exception as e:
                await interaction.response.send_message(f"{GRAFANA_INVITE_GENERIC_HTTP_FAIL}", ephemeral=True)
                logger.error(f"HTTP request failed on invite creation; Exception: {e}; traceback: {traceback.format_exc()}")
                return
            if response_post.status_code == 200:
                try:
                    response_get = requests.get(invites_endpoint, headers=header)
                except Exception as e:
                    await interaction.response.send_message(f"{GRAFANA_INVITE_GENERIC_HTTP_FAIL}", ephemeral=True)
                    logger.error(f"HTTP request failed on invite url retrieval; Exception: {e}; traceback: {traceback.format_exc()}")
                    return
                if response_get.status_code == 200:
                    exists, url = check_invites(response_get.json(), name)
                    if not url:
                        await interaction.response.send_message(f"{GRAFANA_INVITE_GENERIC_HTTP_FAIL}", ephemeral=True)
                        logger.error(f"Did not get an URL for created user: {name}")
                        return
                    await interaction.response.send_message(f"{GRAFANA_INVITE_SUCCESS}: ```{url}```", ephemeral=True)
                    logger.info(f"Generated invite for user: {name}, url: {url}")
                    return
                else:
                    await interaction.response.send_message(f"{GRAFANA_INVITE_GENERIC_HTTP_FAIL}", ephemeral=True)
                    logger.error(f"Did not receive proper response for list of invites. Status: {response_get.status_code}, Text: {response_get.text}")
                    return
            elif response_post.status_code == 412:
                await interaction.response.send_message(f"{GRAFANA_INVITE_USER_ALREADY_EXISTS}: `{name}`", ephemeral=True)
                logger.warning(f"Tried to create an invite for already existing user: {name}")
                return
            else:
                await interaction.response.send_message(f"{GRAFANA_INVITE_GENERIC_HTTP_FAIL}", ephemeral=True)
                logger.error(f"Did not receive proper response for create invite. Status: {response_get.status_code}, Text: {response_get.text}")
                return
    except Exception as e:
        await interaction.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {name}; traceback: {traceback.format_exc()}")

@bot.tree.command(name="match_history_add", description=f"{MATCH_HISTORY_ADD_DESCRIPTION}.")
@discord.app_commands.describe(
    data=f"{MATCH_HISTORY_ADD_PARAMETER_DESCRIPTION}"
)
@commands.has_any_role(*unpack_matching_conf()) # only for sectorial | глава
async def match_history_add(interaction: discord.Interaction, data:str): # data: mm.dd.yyyy;csl_yehv1;SLS;-;100/0;120/23;discord.gg/channel/1231313;youtube;tactics
    logger.info(f"Received match_history_add: {data}, from user: {interaction.user.name} <@{interaction.user.id}>")
    parse_data = data.split(';')
    parsed_data_dict = {
        "date": None,
        "opponent": None,
        "mercs": None,
        "ticket_us_r1": None,
        "ticket_op_r1": None,
        "ticket_diff_r1": None,
        "ticket_us_r2": None,
        "ticket_op_r2": None,
        "ticket_diff_r2": None,
        "layer": None,
        "vods": None,
        "match_status": None,
        "tactics": None,
        "event_url": None,
        "ignore": 0,
        "event_name": None
    }
    errors = []
    try:
        parsed_data_dict["date"] = datetime.strptime(parse_data[0], "%d.%m.%Y").date()
    except Exception as e:
        errors.append(e)
    try:
        parsed_data_dict["event_url"] = parse_data[6]
        match = re.match(r"https?://discord\.com/channels/\d+/(\d+)", parsed_data_dict["event_url"])
        channel_id = int(match.group(1))
        channel = await bot.fetch_channel(channel_id)
        parsed_data_dict["event_name"] = channel.name
    except Exception as e:
        errors.append(e)
    try:
        parsed_data_dict["ticket_us_r1"], parsed_data_dict["ticket_op_r1"] = parse_data[4].split('/')
        parsed_data_dict["ticket_us_r2"], parsed_data_dict["ticket_op_r2"] = parse_data[5].split('/')
        parsed_data_dict["ticket_diff_r1"] = int(parsed_data_dict["ticket_us_r1"]) - int(parsed_data_dict["ticket_op_r1"])
        parsed_data_dict["ticket_diff_r2"] = int(parsed_data_dict["ticket_us_r2"]) - int(parsed_data_dict["ticket_op_r2"])
        parsed_data_dict["match_status"] = (
            'W' if parsed_data_dict["ticket_diff_r1"] + parsed_data_dict["ticket_diff_r2"] > 0
            else 'D' if parsed_data_dict["ticket_diff_r1"] + parsed_data_dict["ticket_diff_r2"] == 0
            else 'L')
    except Exception as e:
        errors.append(e)
    try:
        parsed_data_dict["layer"] = parse_data[1]
        parsed_data_dict["opponent"] = parse_data[2]
        parsed_data_dict["mercs"] = parse_data[3]
        parsed_data_dict["vods"] = parse_data[7]
        parsed_data_dict["tactics"] = parse_data[8]
    except Exception as e:
        errors.append(e)
    if errors:
        msg = f"{MATCH_HISTORY_ADD_DATA_PARSE_ERROR}: {errors}"
        if len(msg) > DISCORD_MAX_MESSAGE_LEN:
            await interaction.response.send_message(f"{msg[:DISCORD_MAX_MESSAGE_LEN-3]}...", ephemeral=True)
        else:  
            await interaction.response.send_message(msg, ephemeral=True)
        logger.error(f"Parsing data failed for match_history_add. Input: {data}, Errors: {errors}")
        return
    try:
        conn = get_db_connection()
    except Exception as e:
        await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
        logger.error(f"Connection failed to db; Exception: {e}; traceback: {traceback.format_exc()}")
        return
    try:
        with conn.cursor() as cursor:
            for value in parsed_data_dict.values():
                if isinstance(value, str):
                    if re.search(r"([`'\";]|--{2,})", value):
                        await interaction.response.send_message(f"{GRAFANA_IGNORE_SQL_INJECT_PROTECTION}: {value}", ephemeral=True)
                        logger.warning(f"Catched SQL inject attempt: {value}. Discord user ID: {interaction.user.id if interaction.user.id else None}")
                        return
            try:
                query = """
                INSERT INTO `match_history` (
                    `date`, opponent, mercs, layer, match_status,
                    ticket_us_r1, ticket_op_r1, ticket_diff_r1,
                    ticket_us_r2, ticket_op_r2, ticket_diff_r2,
                    event_url, vods, tactics, `ignore`, event_name
                ) VALUES (
                    %(date)s, %(opponent)s, %(mercs)s, %(layer)s, %(match_status)s,
                    %(ticket_us_r1)s, %(ticket_op_r1)s, %(ticket_diff_r1)s,
                    %(ticket_us_r2)s, %(ticket_op_r2)s, %(ticket_diff_r2)s,
                    %(event_url)s, %(vods)s, %(tactics)s, %(ignore)s, %(event_name)s
                )
                """
                cursor.execute(query, parsed_data_dict)
                new_row_id = cursor.lastrowid
                conn.commit()
            except pymysql.IntegrityError as e:
                if e.args[0] == 1062:
                    await interaction.response.send_message(f"{MATCH_HISTORY_ADD_DUPLICATE_RECORD_ERROR}: {parsed_data_dict.get("event_name")}", ephemeral=True)
                    logger.error(f"Insert for match_history_add failed - match already exists: {parsed_data_dict.get("event_name")}; Exception: {e}")
                    return
                else:
                    await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                    logger.error(f"Insert for match_history_add failed: {parsed_data_dict}; Exception: {e}; traceback: {traceback.format_exc()}")
                    return
            except Exception as e:
                await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                logger.error(f"Insert for match_history_add failed: {parsed_data_dict}; Exception: {e}; traceback: {traceback.format_exc()}")
                return
            try:
                cursor.execute("SELECT event_name, `date`, layer, opponent FROM match_history WHERE id = %s", (new_row_id,))
                existing = cursor.fetchone()
            except Exception as e:
                await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                logger.error(f"Select inserted row for match_history_add failed, rowID: {new_row_id}; Exception: {e}; traceback: {traceback.format_exc()}")
                return
            await interaction.response.send_message(
                f"### {MATCH_HISTORY_ADD_SUCCESS_TEXT}:\n- {MATCH_HISTORY_ADD_SUCCESS_EVENT_NAME}: {existing['event_name']},\n- {MATCH_HISTORY_ADD_SUCCESS_DATE}: {existing['date']},\n- {MATCH_HISTORY_ADD_SUCCESS_LAYER}: `{existing['layer']}`,\n- {MATCH_HISTORY_ADD_SUCCESS_OPPONENT}: {existing['opponent']}.",
                ephemeral=False
            )
    except Exception as e:
        await interaction.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {data}; traceback: {traceback.format_exc()}")
    finally:
        conn.close()

@bot.tree.command(name="autopost_enable", description=f"{AUTOPOST_ENABLE_DESCRIPTION}.")
@discord.app_commands.describe(
    status=f"{AUTOPOST_ENABLE_STATUS_DESCRIPTION}."
)
@discord.app_commands.choices(
    status=[
        discord.app_commands.Choice(name=f"{AUTOPOST_ENABLE_STATUS_ENABLED}", value=1),
        discord.app_commands.Choice(name=f"{AUTOPOST_ENABLE_STATUS_DISABLED}", value=0)
    ]
)
@commands.has_any_role(*unpack_matching(("UFF", "sectorial")))
async def autopost_enable(interaction: discord.Interaction, status:int):
    logger.info(f"Received autopost_enable: {status}, from user: {interaction.user.name} <@{interaction.user.id}>")
    global autopost_enabled
    try:
        if status == 1:
            autopost_enabled = True
            await interaction.response.send_message(f"{AUTOPOST_ENABLE_COMMAND_ENABLED}.", ephemeral=False)
            if not daily_autopost.is_running():
                await before_daily_autopost()
                daily_autopost.start()
        else:
            autopost_enabled = False
            if daily_autopost.is_running():
                daily_autopost.cancel()
            await interaction.response.send_message(f"{AUTOPOST_ENABLE_COMMAND_DISABLED}.", ephemeral=False)
    except Exception as e:
        await interaction.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {status}; traceback: {traceback.format_exc()}")

@bot.tree.command(name="server_info", description=f"{SERVER_INFO_DESCRIPTION}.")
@discord.app_commands.describe(
    server=f"{SERVER_INFO_SERVER}.",
    ping=f"{SERVER_INFO_PING}.",
    name=f"{SERVER_INFO_NAME}.",
    password=f"{SERVER_INFO_PASSWORD}."
)
@discord.app_commands.choices(
    server=[
        discord.app_commands.Choice(name=f"{SERVER_INFO_SERVER_SCRIMS}", value="scrims"),
        discord.app_commands.Choice(name=f"{SERVER_INFO_SERVER_TRAINING}", value="training"),
        discord.app_commands.Choice(name=f"{SERVER_INFO_SERVER_TEST}", value="test"),
        discord.app_commands.Choice(name=f"{SERVER_INFO_SERVER_CUSTOM}", value="")
    ],
    ping=[
        discord.app_commands.Choice(name=f"{SERVER_INFO_PING_TRUE}", value=1),
        discord.app_commands.Choice(name=f"{SERVER_INFO_PING_FALSE}", value=0)
    ]
)
@commands.has_any_role(*unpack_conf())
async def server_info(interaction: discord.Interaction, server:str, ping:int = 0, name:str = None, password:str = None):
    logger.info(f"Received server_info: {[server,ping,name,password]}, from user: {interaction.user.name} <@{interaction.user.id}>")
    try:
        server_details = Servers.get(server, {})
        if not server_details and not name and not password:
            await interaction.response.send_message(f"{SERVER_INFO_ERROR_NO_INFO}.", ephemeral=True)
            logger.error(f"server_info failed: no server details were provided: {server_details}, {name}, {password}")
        response = f"# {SERVER_INFO_SERVER_STR}: ```{server_details.get("name", name)}``` \n # {SERVER_INFO_PASS_STR}: ```{server_details.get("pass", password)}``` \n"
        if ping == 1:
            try:
                async for message in interaction.channel.history(limit=None, oldest_first=True):
                    if message.author.id == apollo_id:
                        message_link = f"https://discord.com/channels/{interaction.guild.id}/{interaction.channel.id}/{message.id}"
                        break
                    if not message_link:
                        response += f" || {SERVER_INFO_ERROR_FAILED_TO_GET_PINGS} - {SERVER_INFO_APOLLO_NOT_FOUND}|| "
                message = await fetch_message_from_url(interaction, message_link)
                if not message:
                    return
                mentioned_ids = []
                for field in message.embeds[0].fields:
                    if field.name[:10] == '<:accepted' and field.value[:6] == '>>> <@':
                        mentions = field.value[4:].replace('<@', '').replace('>', '')
                        mentioned_ids.extend([int(m) for m in mentions.split('\n') if m])
                ping_str = " ".join(f"<@{member}>" for member in mentioned_ids)
                response += f" || {ping_str} || "
            except Exception as e:
                logger.warning(f"server_info failed to add pings: {e}; traceback: {traceback.format_exc()}")
                response += f" || {SERVER_INFO_ERROR_FAILED_TO_GET_PINGS} || "
        await interaction.response.send_message(f"{SERVER_INFO_SUCCESS}:\n{response}", ephemeral=False)
    except Exception as e:
        await interaction.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {[server, ping, name, password]}; traceback: {traceback.format_exc()}")

@bot.tree.command(name="grafana_update_match", description=f"{GRAFANA_UPDATE_MATCH_COMMAND_DESCRIPTION}.")
@discord.app_commands.describe(
    ignore=f"{GRAFANA_UPDATE_MATCH_IGNORE_VARIABLE}.",
    match_id=f"{GRAFANA_UPDATE_MATCH_MATCH_ID_VARIABLE}.",
    name=f"{GRAFANA_UPDATE_MATCH_NAME_VARIABLE}."
)
@discord.app_commands.choices(
    ignore=[
        discord.app_commands.Choice(name=f"{GRAFANA_IGNORE_VALUE_IGNORE}", value=1),
        discord.app_commands.Choice(name=f"{GRAFANA_IGNORE_VALUE_UNIGNORE}", value=0)
    ]
)
@commands.has_any_role(*unpack_matching_conf()) # only for sectorial | глава
async def grafana_update_match(interaction: discord.Interaction, ignore: int, match_id: int, name:str = None):
    logger.info(f"Received grafana_update_match: {[ignore, match_id, name]}, from user: {interaction.user.name} <@{interaction.user.id}>")
    try:
        conn = get_db_connection()
    except Exception as e:
        await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
        logger.error(f"Connection failed to db; Exception: {e}; traceback: {traceback.format_exc()}")
        return
    try:
        with conn.cursor() as cursor:
            if name:
                if re.search(r"([`'\";]|--{2,})", name):
                    await interaction.response.send_message(f"{GRAFANA_IGNORE_SQL_INJECT_PROTECTION}: {name}", ephemeral=True)
                    logger.warning(f"Catched SQL inject attempt: {name}. Discord user ID: {interaction.user.id if interaction.user.id else None}")
                    return
                try:
                    cursor.execute("UPDATE dblog_matches SET `ignore` = %s, `winner` = %s, `displayName` = %s WHERE id = %s", (ignore, 'UFF' if ignore == 0 else None, name, match_id))
                    conn.commit()
                    cursor.execute("SELECT id, `displayName`, `layerClassname`, `ignore` FROM dblog_matches WHERE id = %s", (match_id))
                    updated = cursor.fetchone()
                    if not updated:
                        await interaction.response.send_message(f"{GRAFANA_IGNORE_NO_ID_FOUND}: {match_id}", ephemeral=True)
                        return
                    updated_ignore = GRAFANA_IGNORE_IGNORED if updated['ignore'] == 1 else GRAFANA_IGNORE_UNIGNORED
                    await interaction.response.send_message(
                    f"### {GRAFANA_UPDATE_MATCH_SUCCESS}:\n- {GRAFANA_INGORE_ID_STR}: `{updated['id']}`,\n- {GRAFANA_UPDATE_MATCH_NAME_STR}: `{updated['displayName']}`,\n- {GRAFANA_UPDATE_MATCH_MAP_STR}: `{updated['layerClassname']}`,\n- {GRAFANA_IGNORE_STATUS_STR}: `{updated_ignore}`.",
                    ephemeral=False
                    )
                except Exception as e:
                    await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                    logger.error(f"Select and update query failed for id: {match_id}; Exception: {e}; traceback: {traceback.format_exc()}")
                    return
            else:
                try:
                    cursor.execute("UPDATE dblog_matches SET `ignore` = %s, `winner` = %s WHERE id = %s", (ignore, 'UFF' if ignore == 0 else None, match_id))
                    conn.commit()
                    cursor.execute("SELECT id, `displayName`, `layerClassname`, `ignore` FROM dblog_matches WHERE id = %s", (match_id))
                    updated = cursor.fetchone()
                    if not updated:
                        await interaction.response.send_message(f"{GRAFANA_IGNORE_NO_ID_FOUND}: {match_id}", ephemeral=True)
                        return
                    updated_ignore = GRAFANA_IGNORE_IGNORED if updated['ignore'] == 1 else GRAFANA_IGNORE_UNIGNORED
                    await interaction.response.send_message(
                    f"### {GRAFANA_UPDATE_MATCH_SUCCESS}:\n- {GRAFANA_INGORE_ID_STR}: `{updated['id']}`,\n- {GRAFANA_UPDATE_MATCH_NAME_STR}: `{updated['displayName']}`,\n- {GRAFANA_UPDATE_MATCH_MAP_STR}: `{updated['layerClassname']}`,\n- {GRAFANA_IGNORE_STATUS_STR}: `{updated_ignore}`.",
                    ephemeral=False
                    )
                except Exception as e:
                    await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                    logger.error(f"Select and update query failed for id: {match_id}; Exception: {e}; traceback: {traceback.format_exc()}")
                    return
    except Exception as e:
        await interaction.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {ignore}, {match_id}, {name}; traceback: {traceback.format_exc()}")
    finally:
        conn.close()

@bot.tree.command(name="grafana_add_match", description=f"{GRAFANA_ADD_MATCH_DESCRIPTION}.")
@discord.app_commands.describe(
    name=f"{GRAFANA_ADD_MATCH_NAME_VARIABLE}.",
    map=f"{GRAFANA_ADD_MATCH_MAP_VARIABLE}.",
    date=f"{GRAFANA_ADD_MATCH_DATE_VARIABLE}."
)
@commands.has_any_role(*unpack_matching_conf()) # only for sectorial | глава
async def grafana_add_match(interaction: discord.Interaction, name:str, map:str, date:str):
    logger.info(f"Received grafana_add_match: {[name, map, date]}, from user: {interaction.user.name} <@{interaction.user.id}>")
    try:
        conn = get_db_connection()
    except Exception as e:
        await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
        logger.error(f"Connection failed to db; Exception: {e}; traceback: {traceback.format_exc()}")
        return
    try:
        with conn.cursor() as cursor:
            if re.search(r"([`'\";]|--{2,})", name):
                await interaction.response.send_message(f"{GRAFANA_IGNORE_SQL_INJECT_PROTECTION}: {name}", ephemeral=True)
                logger.warning(f"Catched SQL inject attempt: {name}. Discord user ID: {interaction.user.id if interaction.user.id else None}")
                return
            if re.search(r"([`'\";]|--{2,})", map):
                await interaction.response.send_message(f"{GRAFANA_IGNORE_SQL_INJECT_PROTECTION}: {map}", ephemeral=True)
                logger.warning(f"Catched SQL inject attempt: {map}. Discord user ID: {interaction.user.id if interaction.user.id else None}")
                return
            if re.search(r"([`'\";]|--{2,})", date):
                await interaction.response.send_message(f"{GRAFANA_IGNORE_SQL_INJECT_PROTECTION}: {map}", ephemeral=True)
                logger.warning(f"Catched SQL inject attempt: {date}. Discord user ID: {interaction.user.id if interaction.user.id else None}")
                return
            try:
                parse_date_check = datetime.strptime(date, "%Y-%m-%d %H:%M")
            except Exception as e:
                await interaction.response.send_message(f"{GRAFANA_ADD_MATCH_INVALID_DATE_FORMAT}", ephemeral=True)
                logger.warning(f"Invalid date format received for grafana_add_match: {date}; Exception: {e}; traceback: {traceback.format_exc()}")
                return
            try:
                cursor.execute("call sp_newMatch(%s, %s, 'UFF', %s)", (map, date, name))
                result = cursor.fetchone()
                conn.commit()
                new_id = list(result.values())[0]
                cursor.execute("SELECT id, `displayName`, `layerClassname` FROM dblog_matches WHERE id = %s", (new_id))
                updated = cursor.fetchone()
                if not updated:
                    await interaction.response.send_message(f"{GRAFANA_IGNORE_NO_ID_FOUND}: {new_id}", ephemeral=True)
                    return
                await interaction.response.send_message(
                f"### {GRAFANA_ADD_MATCH_SUCCESS}:\n- {GRAFANA_INGORE_ID_STR}: `{updated['id']}`,\n- {GRAFANA_UPDATE_MATCH_NAME_STR}: `{updated['displayName']}`,\n- {GRAFANA_UPDATE_MATCH_MAP_STR}: `{updated['layerClassname']}`.",
                ephemeral=False
                )
            except Exception as e:
                await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                logger.error(f"Select and update query failed for args: {[name, map, date]}; Exception: {e}; traceback: {traceback.format_exc()}")
                return
    except Exception as e:
        await interaction.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {[name, map, date]}; traceback: {traceback.format_exc()}")
    finally:
        conn.close()

@bot.tree.command(name="grafana_add_stats", description=f"{GRAFANA_ADD_STATS_DESCRIPTION}.")
@discord.app_commands.describe(
    match_id=f"{GRAFANA_UPDATE_MATCH_MATCH_ID_VARIABLE}.",
    data=f"{GRAFANA_ADD_STATS_DATA_DESCRIPTION}."
)
@commands.has_any_role(*unpack_matching_conf()) # only for sectorial | глава
async def grafana_add_stats(interaction: discord.Interaction, match_id:int, data: discord.Attachment):
    # await interaction.response.defer(thinking=True)  # Tells Discord you're processing
    logger.info(f"Received grafana_add_stats: {match_id}, from user: {interaction.user.name} <@{interaction.user.id}>")
    if not data.filename.lower().endswith(".csv"):
        await interaction.response.send_message(f"{GRAFANA_ADD_STATS_ERROR_NOT_CSV}", ephemeral=True)
        logger.error(f"Got a file not in csv format: {data.filename}")
        return
    try:
        file_bytes = await data.read()
        decoded = file_bytes.decode('utf-8')  # or 'utf-8-sig' if Excel exports with BOM
        # Use csv.Sniffer to detect the delimiter
        sample = decoded[:1024]
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=[',', ';'])
        # Read the CSV using the detected dialect
        reader = csv.reader(io.StringIO(decoded), dialect)
        csv_data = list(reader)
    except Exception as e:
        await interaction.response.send_message(f"{GRAFANA_ADD_STATS_ERROR_PARSING_CSV}", ephemeral=True)
        logger.error(f"Failed to parse csv: {e}; traceback: {traceback.format_exc()}")
        return
    if not csv_data:
        await interaction.response.send_message(f"{GRAFANA_ADD_STATS_ERROR_EMPTY_CSV}", ephemeral=True)
        logger.warning(f"Empty csv file.")
        return
    query_list = []
    try:
        for line in csv_data:
            if re.search(r"([`'\";]|--{2,})", line[0]):
                await interaction.response.send_message(f"{GRAFANA_IGNORE_SQL_INJECT_PROTECTION}: {line[0]}", ephemeral=True)
                logger.warning(f"Catched SQL inject attempt: {line[0]}. Discord user ID: {interaction.user.id if interaction.user.id else None}")
                return
            query_list.append(
                f"call sp_addKDWR({match_id}, fn_getsteamidfromname('{line[0]}'), {line[1]}, {line[2]}, {line[3]}, {line[4]}, {line[5]})"
            )
    except Exception as e:
        await interaction.response.send_message(f"{GRAFANA_ADD_STATS_FAILED_TO_PARSE_CSV}", ephemeral=True)
        logger.error(f"Failed to parse csv: {e}; traceback: {traceback.format_exc()}")
        return
    if not query_list:
        await interaction.response.send_message(f"{GRAFANA_ADD_STATS_ERROR_GETTING_QUERIES}", ephemeral=True)
        logger.warning(f"Empty query list from csv file.")
        return
    try:
        conn = get_db_connection()
    except Exception as e:
        await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
        logger.error(f"Connection failed to db; Exception: {e}; traceback: {traceback.format_exc()}")
        return
    try:
        with conn.cursor() as cursor:
            try:
                for query in query_list:
                    cursor.execute(query)
                    conn.commit()
                await interaction.response.send_message(
                f"### {GRAFANA_ADD_STATS_SUCCESS}:\n -{GRAFANA_ADD_STATS_MATCH_ID_STR}: `{match_id}` \n -{GRAFANA_ADD_STATS_QUERIES_STR}:\n```{'\n'.join(query_list)}```",
                ephemeral=False
                )
            except Exception as e:
                await interaction.response.send_message(f"{GRAFANA_IGNORE_GENERIC_DB_FAIL}", ephemeral=True)
                logger.error(f"Select and update query failed for args: {[match_id, query_list]}; Exception: {e}; traceback: {traceback.format_exc()}")
                return
    except Exception as e:
        await interaction.response.send_message(f"{ERROR_GENERIC}: {e}", ephemeral=True)
        logger.error(f"{ERROR_GENERIC}: {e}; args: {match_id}; traceback: {traceback.format_exc()}")
    finally:
        conn.close()

bot.run(DiscordToken, log_handler=handler, log_level=logging.INFO)