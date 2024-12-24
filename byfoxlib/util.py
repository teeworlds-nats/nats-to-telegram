import logging
import re
from typing import Optional

import nats
import telebot
import yaml

from nats.aio.client import Client
from nats.js import JetStreamContext
from nats.js.errors import NotFoundError

from .emojies import replace_from_emoji
from .model import Config

_log = logging.getLogger(__name__)

__all__ = (
    "Nats",
    "get_config",
    "nats_connect",
    "format_mention",
    "text_format",
    "regex_format",
    "generate_message_reply",
    "generate_message",
    "check_media"
)


class Nats:
    def __init__(self, tuple_nats: tuple[Client, JetStreamContext]) -> None:
        self.ns, self.js = tuple_nats

    async def check_stream(self, namespace: str, **kwargs):
        try:
            await self.js.stream_info(namespace)
        except NotFoundError:
            pass
        else:
            await self.js.delete_stream(namespace)
        await self.js.add_stream(name=namespace, **kwargs)

    async def send_message(
            self,
            write_path: list[str],
            text: str,
            message: telebot.types.Message
    ) -> None:
        for path in write_path:
            await self.js.publish(
                path.format(message_thread_id=message.message_thread_id),
                text.encode(),
                headers={
                    "Nats-Msg-Id": f"{message.from_user.id}_{message.date}_{hash(text)}_{message.chat.id}"
                }
            )


def get_config(modal):
    with open('config.yaml', encoding="utf-8") as fh:
        data = yaml.load(fh, Loader=yaml.FullLoader)
    _yaml = modal(**data) if data is not None else None
    if _yaml is not None:
        _log.info("config loaded from yaml")
        return _yaml


def text_replace(msg: str) -> str:
    return msg.replace("\\", "\\\\").replace("\'", "\\\'").replace("\"", "\\\"").replace("\n", " ")


def generate_message(env_text: str,  _msg: telebot.types.Message, text: str = None) -> str:
    return env_text.format(
        name=_msg.from_user.first_name + (_msg.from_user.last_name or ''),
        text=text_replace(replace_from_emoji(_msg.text)) if text is None else text
    )


def generate_message_reply(reply_string: str, env_text: str, _msg: telebot.types.Message, text: str = None) -> str | None:
    return reply_string.format(
        replay_id=_msg.reply_to_message.id,
        replay_msg=text_replace(generate_message(env_text, _msg.reply_to_message))
    ) if _msg.reply_to_message.text is not None else text


def check_media(env: Config, message: telebot.types.Message) -> str:
    if message.sticker is not None:
        return generate_message(
            env.text,
            message,
            env.sticker_string.format(
                sticker_emoji=replace_from_emoji(message.sticker.emoji)
            )
        )
    for i in [
        "video",
        "photo",
        "audio",
        "voice"
    ]:
        if getattr(message, i) is not None:
            return generate_message(env.text, getattr(env, i + '_string'))
    return ""


async def nats_connect(env: Config) -> tuple[Client, JetStreamContext]:
    nc = await nats.connect(env.nats.servers, user=env.nats.user, password=env.nats.password)
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
