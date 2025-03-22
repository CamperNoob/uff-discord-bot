import discord
from discord.ext import commands
import logging
from tokens import DiscordToken
import difflib
import traceback
from collections import defaultdict
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
        logger.info(f"Error syncing commands: {e}")

@bot.tree.command(name="missing_mentions", description=f"{MISSING_MENTIONS_COMMAND_DESCRIPTION}.")
@discord.app_commands.describe(
    role=f"{MISSING_MENTIONS_ROLE_DESCRIPTION}.",
    message_link=f"{MISSING_MENTIONS_MESSAGE_LINK_DESCRIPTION}.",
    role2=f"{MISSING_MENTIONS_ADDITIONAL_ROLE_DESCRIPTION} {MISSING_MENTIONS_ROLE_DESCRIPTION}.",
    role3=f"{MISSING_MENTIONS_ADDITIONAL_ROLE_DESCRIPTION} {MISSING_MENTIONS_ROLE_DESCRIPTION}.",
)
@commands.has_permissions(administrator=True)
async def missing_mentions(ctx: discord.Interaction, role: discord.Role, message_link: str = None, role2: discord.Role = None, role3: discord.Role = None):
    logger.info(f"Received missing_mentions: {message_link}, {[role.name, role2.name if role2 else None, role3.name if role3 else None]}, from user: {ctx.user.name} <@{ctx.user.id}>")
    apollo_id = 475744554910351370
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
        logger.info(f"{ERROR_GENERIC}: {e}; args: {message_link}; {type(role)}; {type(role2)}; {type(role3)}; traceback: {traceback.format_exc()}")

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
@commands.has_permissions(administrator=True)
async def generate_roster(ctx: discord.Interaction, message_link: str):
    guild = ctx.guild
    emoji_map = {
        'sl':discord.utils.get(guild.emojis, name='role_sl') or 'SL',
        'engi':discord.utils.get(guild.emojis, name='role_engi') or 'Engineer',
        'rifl':discord.utils.get(guild.emojis, name='role_rifleman') or 'Rifleman',
        'rifleman':discord.utils.get(guild.emojis, name='role_rifleman') or 'Rifleman',
        'pilot':discord.utils.get(guild.emojis, name='role_pilot') or 'Pilot',
        'mortar':discord.utils.get(guild.emojis, name='role_mortar') or 'Mortar',
        'mg':discord.utils.get(guild.emojis, name='role_mg') or 'MG',
        'hmg':discord.utils.get(guild.emojis, name='role_mg') or 'MG',
        'medic':discord.utils.get(guild.emojis, name='role_medic') or 'Medic',
        'med':discord.utils.get(guild.emojis, name='role_medic') or 'Medic',
        'sniper':discord.utils.get(guild.emojis, name='role_marksman') or 'Marksman',
        'marksman':discord.utils.get(guild.emojis, name='role_marksman') or 'Marksman',
        'lat':discord.utils.get(guild.emojis, name='role_lat') or 'LAT',
        'hat':discord.utils.get(guild.emojis, name='role_hat') or 'HAT',
        'gp':discord.utils.get(guild.emojis, name='role_gp') or 'GP',
        'sap':discord.utils.get(guild.emojis, name='role_sapper') or 'Sapper',
        'sapper':discord.utils.get(guild.emojis, name='role_sapper') or 'Sapper',
        'crewman':discord.utils.get(guild.emojis, name='role_crewman') or 'Crewman',
        'crew':discord.utils.get(guild.emojis, name='role_crewman') or 'Crewman',
        'cr':discord.utils.get(guild.emojis, name='role_crewman') or 'Crewman',
        'autorifl':discord.utils.get(guild.emojis, name='role_autorifleman') or 'Automatic Rifleman',
        'autorifleman':discord.utils.get(guild.emojis, name='role_autorifleman') or 'Automatic Rifleman',
        'scout':discord.utils.get(guild.emojis, name='role_scout') or 'Scout',
        'ifv':discord.utils.get(guild.emojis, name='map_wheelifv') or 'IFV',
        'tank':discord.utils.get(guild.emojis, name='map_tank') or 'Tank',
        'truck':discord.utils.get(guild.emojis, name='map_truck') or 'Truck',
        'peh':discord.utils.get(guild.emojis, name='map_truck') or 'Truck',
        'logi':discord.utils.get(guild.emojis, name='map_logitruck') or 'Logi',
        'rws':discord.utils.get(guild.emojis, name='map_jeeprws') or 'RWS',
        'mrap':discord.utils.get(guild.emojis, name='map_jeep') or 'MRAP',
        'heli':discord.utils.get(guild.emojis, name='map_heli') or 'Helicopter',
        'helicopter':discord.utils.get(guild.emojis, name='map_heli') or 'Helicopter',
        'boat':discord.utils.get(guild.emojis, name='map_boat') or 'Boat',
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
            await ctx.response.send_message(f"{GENERATE_ROSTER_SUCCESS}:\n{'\n'.join(return_text)}")
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
@commands.has_permissions(administrator=True)
async def ping_tentative(ctx: discord.Interaction, message_link: str = None):
    logger.info(f"Received ping_tentative: {message_link}, from user: {ctx.user.name} <@{ctx.user.id}>")
    apollo_id = 475744554910351370
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
        logger.info(f"{ERROR_GENERIC}: {e}; args: {message_link}; traceback: {traceback.format_exc()}")

bot.run(DiscordToken, log_handler=handler, log_level=logging.INFO)