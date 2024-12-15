from typing import Any

from pydantic import BaseModel, Field


class Path(BaseModel):
    chat_id: str
    thread_id: int = None
    pattern: str = None
    read: str
    tokens: Any


class Nats(BaseModel):
    servers: str | list = Field("127.0.0.1", alias="server")
    user: str = None
    password: str = None
    enable_process_messages: bool = Field(True)
    write_path: list[str] = None  # path where it writes what the bot reads
    paths: list[Path]


class Env(BaseModel):
    nats: Nats

    log_level: str = Field("info")
    text: str = Field("[TG] {name}: {text}")
    sticker_string: str = Field("[STICKER {sticker_emoji}]")
    video_string: str = Field("[MEDIA]")
    photo_string: str = Field("[PHOTO]")
    audio_string: str = Field("[AUDIO]")
    voice_string: str = Field("[VOICE]")
    reply_string: str = Field("[Reply {replay_id}] {replay_msg}")
    edit_string: str = Field("[EDIT {msg_id}]")
    repetition: int = Field(100)


class Msg(BaseModel):
    server_name: str | None
    args: list
    message_thread_id: str | int | None


class MsgEvents(BaseModel):
    server_name: str
    rcon: str
