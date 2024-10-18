import logging
import os
import re
from typing import TypeVar, Callable, Optional

import nats
import yaml
from nats.aio.client import Client
from nats.js import JetStreamContext

DataClassT = TypeVar("DataClassT", bound="BaseModel")
_log = logging.getLogger(__name__)


__all__ = (
    "get_data_env",
    "nats_connect",
    "format_mention",
    "text_format",
    "regex_format"
)


def get_env(modal: DataClassT) -> DataClassT:
    return modal(**os.environ)


def get_data_env(modal: DataClassT, func: Callable = get_env) -> DataClassT:
    if os.path.exists("./config.yaml"):
        with open('./config.yaml', encoding="utf-8") as fh:
            data = yaml.load(fh, Loader=yaml.FullLoader)
        _yaml = modal(**data) if data is not None else None
        if _yaml is not None:
            _log.info("config loaded from yaml")
            return _yaml
    _log.info("config loaded from env or custom")
    return func(modal)


async def nats_connect(env: DataClassT) -> tuple[Client, JetStreamContext]:
    nc = await nats.connect(
        servers=env.nats_server,
        user=env.nats_user,
        password=env.nats_password
    )
    js = nc.jetstream()
    _log.info("nats connected")
    return nc, js


def format_mention(nickname: Optional[str]) -> Optional[str]:
    """
    Formats the nickname to protect against spam mentions in chat.

    If the nickname contains '@' anywhere in the string, but is not exactly '@',
    and contains more than one character, add a hyphen after the '@' character to ensure proper formatting
    for a ping or mention. This prevents incorrect formatting for a single '@' character and
    ensures proper formatting for nicknames with an '@' character in the middle or at the end.
    Args:
        nickname (str): The nickname to format.

    Returns:
        str: The formatted nickname.
    """
    if nickname is None:
        return
    if '@' in nickname and len(nickname) > 1:
        return nickname.replace('@', '@-')
    return nickname


def text_format(text: str, text_list: Optional[list]):
    if text_list is None:
        return text

    text_ = str(text)
    for r, t in text_list:
        text_ = text_.replace(r, t, 1)

    return text_


def regex_format(text: str, regex_: Optional[list[re.Pattern]]):
    if regex_ is None:
        return text

    text_ = str(text)
    for reg, to in regex_:
        regex = reg.findall(text)
        if not regex:
            continue

        text_ = text_.replace(regex[0], to, 1)
    return text_

