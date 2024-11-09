from typing import Optional, Union

from pydantic import BaseModel, Field


class CustomCommands(BaseModel):
    slash_command: str
    tw_command: str
    args: list
    count_args: int
    example_str: str


class Nats(BaseModel):
    servers: str | list = Field("127.0.0.1", alias="server")
    user: str = None
    password: str = None

class Util(BaseModel):
    tg_token: str = None
    chat_id: str = None
    logger_thread_id: int | str = None

class Env(BaseModel):
    TELEGRAM_BOT_TOKENS: str | list = None
    chat_id: str = None

    util: Util = None
    nats: Nats

    log_level: str = Field("info")
    text: str = Field("[TG] {name}: {text}")
    sticker_string: str = Field("[STICKER {sticker_emoji}]")
    video_string: str = Field("[MEDIA]")
    photo_string: str = Field("[PHOTO]")
    audio_string: str = Field("[AUDIO]")
    voice_string: str = Field("[VOICE]")
    reply_string: str = Field("[Reply {replay_id}] {replay_msg}")
    repetition: int = Field(100)

    admin_ids: list = Field([])
    positions_custom_name: list = Field(["[admin]", "[mod]"])
    custom: list = Field([])


class Msg(BaseModel):
    server_name: Optional[str]
    name: Optional[str]
    message_thread_id: Union[int, str]
    regex_type: str
    text: Optional[str]


class MsgEvents(BaseModel):
    server_name: str
    rcon: str


class Buffer(BaseModel):
    string: str = Field("")
    old_message_hash: int = Field(0)
    count: int = Field(0)
