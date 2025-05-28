from enum import Enum
import logging
import requests

from restic_scheduled_backups.config_def import NtfyConfig

import restic_scheduled_backups.common

logger = logging.getLogger(__name__)

class NtfyPriorityLevel(str, Enum):
    MAX = "max"
    HIGH = "high"
    DEFAULT = "default"
    LOW = "low"
    MIN = "min"


def ntfy_message(config:NtfyConfig, title:str, message: str, priority: NtfyPriorityLevel = NtfyPriorityLevel.DEFAULT, tags:list[str]=[]) -> None:
    """ Sends a ntfy message

    Args:
        config (NtfyConfig): ntfy config
        title (str): Message Title
        message (str): message to send
        priority (NtfyPriorityLevel, optional): priority level. Defaults to NtfyPriorityLevel.DEFAULT.
        tags (list[str], optional): list of tags to send with the message. Defaults to [].
    """
    if config is not None:
        headers = {
            "Title": title,
            "Priority": priority.value,
            "Tags": ",".join(tags),
            "Authorization": f"Bearer {config.token}"
        }
        
        try:
            response = requests.post(f"{config.topic_url}", headers=headers, data=message)

            if response.status_code == 200 or response.status_code == 201 or response.status_code ==  204:
                logger.debug(f"ntfy message sent" )
            else:
                logger.error(f"Unable to send ntfy message: {response.status_code} - {response.text}")
        except requests.exceptions.RequestException as re:
            logger.exception("Failed to send ntfy message")
    
