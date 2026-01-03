from configs.tokens import amp_api_token, amp_allowed_reboot_instances
import ampapi as amp
from discord.app_commands import Choice
from typing import Tuple
from discord import Interaction

_params = amp.dataclass.APIParams(**amp_api_token)

API_INSTANCE_CACHE = {}

async def get_amp_servers(
        interaction: Interaction, # unused, but required by discord interaction
        current: str # unused, but required by discord interaction
) -> list[Choice[str]]:
    _bridge = amp.Bridge(api_params=_params)
    ADS: amp.AMPControllerInstace = amp.AMPControllerInstance()

    global API_INSTANCE_CACHE

    await ADS.get_instances(format_data=True)

    allowed_reboot_instances = {}

    allowed_reboot_instance_names = [item["InstanceName"] for item in amp_allowed_reboot_instances]

    for instance in list(ADS.instances):
        if instance.instance_name in allowed_reboot_instance_names:
            allowed_reboot_instances[instance.instance_name] = {
                "instance": instance,
                "instance_name": instance.instance_name,
                "friendly_name": instance.friendly_name,
                "online": instance.metrics.active_users["raw_value"] if (instance.metrics and instance.metrics.active_users) else None
            }
    
    API_INSTANCE_CACHE.clear()
    API_INSTANCE_CACHE.update(allowed_reboot_instances)
    
    return [
        Choice(name=f"{item["friendly_name"]} (online: {item["online"] if item["online"] is not None else 'None'})", value=key)
        for key, item in allowed_reboot_instances.items()
    ]

async def send_reboot_server(instance_name: str) -> Tuple[bool, Exception | None, str | None]:
    _bridge = amp.Bridge(api_params=_params)

    global API_INSTANCE_CACHE

    if instance_name not in API_INSTANCE_CACHE:
        return False, ValueError(f"Error: server not found with name {instance_name}"), None

    if API_INSTANCE_CACHE[instance_name] and API_INSTANCE_CACHE[instance_name]["online"] > 0:
        return False, InterruptedError(f"Error: cannot restart unempty server. Try again after all users left."), None

    try:
        instance = API_INSTANCE_CACHE[instance_name]["instance"]
        await instance.restart_instance()
    except Exception as e:
        return False, e, None
    else:
        return True, None, API_INSTANCE_CACHE[instance_name]["friendly_name"]