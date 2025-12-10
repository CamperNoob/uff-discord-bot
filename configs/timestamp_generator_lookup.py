from zoneinfo import ZoneInfo
from discord.app_commands import Choice

TIMESTAMP_FORMATS = {
    "long": {
        "example": "Wednesday, December 10, 2025 at 6:00 PM",
        "format_string": "<t:{unixtimestamp}:F>"
    },
    "long with time":
    {
        "example": "December 10, 2025 at 6:00 PM",
        "format_string": "<t:{unixtimestamp}:f>"
    },
    "long date":
    {
        "example": "December 10, 2025",
        "format_string": "<t:{unixtimestamp}:D>"
    },
    "short date":
    {
        "example": "12/10/2025",
        "format_string": "<t:{unixtimestamp}:d>"
    },
    "time":
    {
        "example": "6:00 PM",
        "format_string": "<t:{unixtimestamp}:t>"
    },
    "time with seconds":
    {
        "example": "6:00:00 PM",
        "format_string": "<t:{unixtimestamp}:T>"
    },
    "countdown":
    {
        "example": "in 7 hours",
        "format_string": "<t:{unixtimestamp}:R>"
    },
    "short timestamp":
    {
        "example": "12/10/2025, 6:00 PM",
        "format_string": "<t:{unixtimestamp}:s>"
    },
    "short timestamp with seconds":
    {
        "example": "12/10/2025, 6:00:00 PM",
        "format_string": "<t:{unixtimestamp}:S>"
    }
}

def get_formats():
    return [
        Choice(name=value["example"], value=key)
        for key, value in TIMESTAMP_FORMATS.items()
    ]

def get_format_from_key(key):
    return TIMESTAMP_FORMATS.get(key, {}).get("format_string")

TIMEZONE_MAP = {
    -11: {"show_name": "UTC-11 (Niue)", "zoneinfo": ZoneInfo("Pacific/Niue")},
    -10: {"show_name": "UTC-10 (Honolulu)", "zoneinfo": ZoneInfo("Pacific/Honolulu")},
    -9:  {"show_name": "UTC-9 (Anchorage)",  "zoneinfo": ZoneInfo("America/Anchorage")},
    -8:  {"show_name": "UTC-8 (PST)", "zoneinfo": ZoneInfo("America/Los_Angeles")},
    -7:  {"show_name": "UTC-7 (MST)", "zoneinfo": ZoneInfo("America/Denver")},
    -6:  {"show_name": "UTC-6 (CST)", "zoneinfo": ZoneInfo("America/Chicago")},
    -5:  {"show_name": "UTC-5 (EST)", "zoneinfo": ZoneInfo("America/New_York")},
    -4:  {"show_name": "UTC-4 (Halifax)", "zoneinfo": ZoneInfo("America/Halifax")},
    -3:  {"show_name": "UTC-3 (Buenos_Aires)", "zoneinfo": ZoneInfo("America/Argentina/Buenos_Aires")},
    -2:  {"show_name": "UTC-2 (Noronha)", "zoneinfo": ZoneInfo("America/Noronha")},
    -1:  {"show_name": "UTC-1 (Azores)", "zoneinfo": ZoneInfo("Atlantic/Azores")},
     0:  {"show_name": "UTC+0 (UTC)", "zoneinfo": ZoneInfo("UTC")},
     1:  {"show_name": "UTC+1 (Berlin)", "zoneinfo": ZoneInfo("Europe/Berlin")},
     2:  {"show_name": "UTC+2 (Kyiv)", "zoneinfo": ZoneInfo("Europe/Kyiv")},
     3:  {"show_name": "UTC+3 (Istanbul)", "zoneinfo": ZoneInfo("Europe/Istanbul")},
     4:  {"show_name": "UTC+4 (Dubai)", "zoneinfo": ZoneInfo("Asia/Dubai")},
     5:  {"show_name": "UTC+5 (Karachi)", "zoneinfo": ZoneInfo("Asia/Karachi")},
     6:  {"show_name": "UTC+6 (Almaty)", "zoneinfo": ZoneInfo("Asia/Almaty")},
     7:  {"show_name": "UTC+7 (Bangkok)", "zoneinfo": ZoneInfo("Asia/Bangkok")},
     8:  {"show_name": "UTC+8 (Shanghai)", "zoneinfo": ZoneInfo("Asia/Shanghai")},
     9:  {"show_name": "UTC+9 (Tokyo)", "zoneinfo": ZoneInfo("Asia/Tokyo")},
    10:  {"show_name": "UTC+10 (Sydney)", "zoneinfo": ZoneInfo("Australia/Sydney")},
    11:  {"show_name": "UTC+11 (Sakhalin)", "zoneinfo": ZoneInfo("Asia/Sakhalin")},
    12:  {"show_name": "UTC+12 (Auckland)", "zoneinfo": ZoneInfo("Pacific/Auckland")},
}

def get_timezones():
    return [
        Choice(name=value["show_name"], value=key)
        for key, value in TIMEZONE_MAP.items()
    ]

def get_timezone_from_key(key):
    return TIMEZONE_MAP.get(key, {}).get("zoneinfo")