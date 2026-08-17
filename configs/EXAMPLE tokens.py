from google.genai import types
import discord
from datetime import datetime

DiscordToken = '' #Discord developers -> App -> Bot -> TOKEN
MySQL = {
    "host": "", #ip
    "port": 0000, #port
    "user": "", #db username
    "password": "", #db password
    "database": "" #db name
}
Grafana = {
    "url": "https://grafana.url.link/",
    "token": ""
}
Servers = {
    "scrims": {
        "name": "uff scrims",
        "pass": "123456"
    },
    "training": {
        "name": "uff training",
        "pass": "654321"
    },
    "test": {
        "name": "uff test",
        "pass": "123654"
    }
}
ApolloID = 1234567890
GeminiAPI = ''
GeminiModel = 'gemini-3.1-flash-lite'
GeminiAPIInstruction = {
    "1": ["You are a cat named Neko."]
}
TempVoiceChannels = [   # Voice channels which act as a hub for temporary voices
    1234567890
]
amp_api_token = {
    "url": "https://127.0.0.1:8080",
    "user": "admin",
    "password": "admin"
}

amp_allowed_reboot_instances = [
    {"InstanceName": "Server01"},
    {"InstanceName": "Server02"},  
]
AutoBanChannels = [ # text channels, from which the user is banned when written into
    1234567890
]
AutoBanRoleBlacklist = [ # role that user must NOT have in order to be autobanned from writing into autoban channel
    1234567890
]

zugzwang = {
    "id": 12345678,
    "word_limit": 10,
    "dictionary": [
        "try",
        "using",
        "warning"
    ],
    "replies": [
        "tenor.com/gif_1"
    ],
    "only_channel": 1234567
}

discord_status = {
    "status": discord.Status.online, # online, offline, idle, dnd, do_not_disturb, invisible
    "activity": {
        # https://discordpy.readthedocs.io/en/stable/api.html?highlight=change_presence#discord.Activity.application_id
        "type": discord.ActivityType.watching, # competing, custom, listening, playing, streaming, unknown, watching
        "application_id": None, # The application ID of the game.
        "assets": None, # A dictionary representing the images and their hover text of an activity. large_image, large_text, large_url, small_image, small_text, small_url
        "buttons": None, # A list of strings representing the labels of custom buttons shown in a rich presence.
        "details": None, # The detail of the user’s current activity.
        "details_url": None, # A URL that is linked to when clicking on the details text of the activity.
        "emoji": None, # The emoji that belongs to this activity.
        "end": None, # When the user will stop doing this activity in UTC, if applicable.
        "large_image_text": None, # Returns the small image asset hover text of this activity, if applicable.
        "large_image_url": None, # Returns a URL pointing to the large image asset of this activity, if applicable.
        "name": None, # The name of the activity.
        "party": None, # A dictionary representing the activity party. id, size (list of current size, max size)
        "platform": None, # The user’s current platform.
        "small_image_text": None, # Returns the large image asset hover text of this activity, if applicable.
        "small_image_url": None, # Returns a URL pointing to the small image asset of this activity, if applicable.
        "start": datetime(2025, 1, 1, 12, 29, 0), # When the user started doing this activity in UTC, if applicable.
        "state": None, # The user’s current state. For example, “In Game”.
        "state_url": None, # A URL that is linked to when clicking on the state text of the activity.
        "status_display_type": None, # Determines which field from the user’s status text is displayed in the members list.
        "timestamps": None, # A dictionary of timestamps. start (ms from unix epoch when activity started), end (ms from unix epoch when activity will end)
        "url": None # A stream URL that the activity could be doing.
    }
}