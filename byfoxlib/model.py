from typing import Any

from pydantic import BaseModel, Field


class Path(BaseModel):
    chat_id: str
    thread_id: int = None
    pattern: str = None
    read: str
    write: list[str] = Field("tw.econ.write.{message_thread_id}")
    tokens: Any


class Nats(BaseModel):
    servers: str | list = Field("127.0.0.1", alias="server")
    user: str = None
    password: str = None
    enable_process_messages: bool = Field(True)
    paths: list[Path]


class Config(BaseModel):
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


class Args(BaseModel):
    server_name: str | None
    message_thread_id: int | None


class Msg(BaseModel):
    value: list
    args: Args



class MsgEvents(BaseModel):
    server_name: str
    rcon: str
