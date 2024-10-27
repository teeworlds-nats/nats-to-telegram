import asyncio
import json
import logging
from itertools import cycle

import telebot.types
from dotenv import load_dotenv
from nats.js import JetStreamContext
from nats.aio.msg import Msg as MsgNats
from nats.js.errors import NotFoundError
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException
from telebot.util import split_string

from model import Env, Msg, Buffer, MsgEvents
from util import nats_connect, get_data_env, generate_message_reply, generate_message, check_media


load_dotenv()
env: Env = get_data_env(Env)

bots = [
    AsyncTeleBot(token)
    for token in env.TELEGRAM_BOT_TOKENS
]  # Bypass rate limit
bot = bots[0]
bot_moderator = AsyncTeleBot(env.util_tg_token)

logging.info("count bots: %s", len(bots))
bots = cycle(bots)

js: JetStreamContext = None
buffer: dict[int | str, Buffer] = {}

logging.basicConfig(format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log = logging.getLogger("root")
log.setLevel(getattr(logging, env.log_level.upper()))


async def send_msg_telegram(text: str, thread_id: int) -> bool:
    try:
        await next(bots).send_message(env.chat_id, text, message_thread_id=thread_id)
    except ApiTelegramException as err:
        logging.debug("ApiTelegramException occurred: %s", err)
    else:
        return True
    return False

async def send_message(text: str, message) -> None:
    await js.publish(
        f"tw.econ.write.{message.message_thread_id}",
        text.encode(),
        headers={
            "Nats-Msg-Id": f"{message.from_user.id}_{message.date}_{hash(text)}_{message.chat.id}"
        }
    )


async def events_handler_telegram(message: MsgNats):
    """Takes a message from nats and sends it to telegram."""

    msg = MsgEvents(**json.loads(message.data.decode()))
    logging.debug("tw.events > %s", msg)
    await bot_moderator.send_message(
        env.chat_id,
        f"{msg.server_name}: `{msg.rcon}`",
        message_thread_id=env.message_thread_id
    )


async def message_handler_telegram(message: MsgNats):
    """Takes a message from nats and sends it to telegram."""
    msg = Msg(**json.loads(message.data.decode()))
    logging.debug("tw.%s > %s", msg.message_thread_id, msg.text)

    if buffer.get(msg.message_thread_id) is None:
        buffer[msg.message_thread_id] = Buffer()

    text = f"{msg.name}: {msg.text}" if msg.name is not None and msg.name != "" else f"{msg.text}"

    buffer[msg.message_thread_id].string += text + "\n"
    buffer[msg.message_thread_id].count += 1

    text_hash = hash(text)

    if buffer[msg.message_thread_id].old_message_hash != text_hash or buffer[msg.message_thread_id].count >= env.repetition:
        buffer[msg.message_thread_id].old_message_hash = text_hash

        list_text = [buffer[msg.message_thread_id].string]
        buffer[msg.message_thread_id].count = 0

        if len(buffer[msg.message_thread_id].string) > 4000:
            list_text = split_string(buffer[msg.message_thread_id].string, 2000)

        for i in list_text:
            if await send_msg_telegram(i, msg.message_thread_id):
                buffer[msg.message_thread_id].string = ""

    await message.term()


async def main():
    global js
    nc, js = await nats_connect(env)

    try:
        await js.stream_info("tw")
    except NotFoundError:
        pass
    else:
        await js.delete_stream("tw")

    await js.add_stream(name='tw', subjects=['tw.*', 'tw.*.*', 'tw.*.*.*'], max_msgs=1000, max_age=30)

    await js.subscribe("tw.tg.*", "telegram_bot", cb=message_handler_telegram)
    await js.subscribe("tw.events", "moderator_bot", cb=events_handler_telegram)
    logging.info("nats js subscribe \"tw.tg.*\"")
    logging.info("bot is running")

    await bot.infinity_polling(logger_level=logging.DEBUG)


@bot.message_handler(content_types=["photo", "sticker", "sticker", "audio", "voice"])
async def echo_media(message: telebot.types.Message):
    if js is None or message is None:
        return

    text = ""

    if message.reply_to_message is not None:
        reply = generate_message_reply(env.reply_string, env.text, message)
        text = f"say \"{reply[:255]}\";" if reply is not None else ""
    text += f"say \"{check_media(env, message)[:255]}\""

    await send_message(text, message)


@bot.message_handler(content_types=["text"])
async def echo_text(message: telebot.types.Message):
    if js is None or message is None:
        return

    text = ""

    if message.reply_to_message is not None:
        reply = generate_message_reply(env.reply_string, env.text, message)
        text += f"say \"{reply[:255]}\";" if reply is not None else ""
    text += f"say \"{generate_message(env.text, message)[:255]}\""

    await send_message(text, message)


if __name__ == '__main__':
    asyncio.run(main())
