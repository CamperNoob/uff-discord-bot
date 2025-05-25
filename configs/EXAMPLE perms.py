roles = {
    "guild1": {
        "clanrep":0000000000000000001,
        "administrator":0000000000000000002,
        "cmd":0000000000000000003
    },
    "guild2": {
        "clanrep":0000000000000000001,
        "administrator":0000000000000000002,
        "cmd":0000000000000000003
    }
}

def unpack(*args):
    unpacked = []
    for arg in args:
        unpacked.extend(arg.values())
    return unpacked

def unpack_matching(*args):
    unpacked = []
    for guild_key, role_key in args:
        guild_roles = roles.get(guild_key, {})
        role_id = guild_roles.get(role_key)
        if role_id is not None:
            unpacked.append(role_id)
    return unpacked

# Usage: @commands.has_any_role(*unpack_conf())
def unpack_conf():
    return unpack(*roles.values())

# Usage: @commands.has_any_role(*unpack_matching_conf())
def unpack_matching_conf():
    curr_list = [
        ("guild1", "clanrep"),
        ("guild2", "clanrep"),
    ]
    return unpack_matching(*curr_list)