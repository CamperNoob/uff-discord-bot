from discord.app_commands import Choice

_GIF_LIST=[
    {"name": "gif1", "value": "https://tenor.com/gif1.gif"},
]

def get_gifs():
    return [
        Choice(name=entry["name"], value=entry["value"])
        for entry in _GIF_LIST
    ]