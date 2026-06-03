from google.genai import types

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