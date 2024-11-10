import asyncio
import json
import logging
from itertools import cycle

import telebot.types
from dotenv import load_dotenv
from nats.aio.msg import Msg as MsgNats
from telebot.async_telebot import AsyncTeleBot
from telebot.util import split_string

from model import Env, Msg, Buffer
from util import nats_connect, get_data_env, generate_message_reply, generate_message, check_media, send_msg_telegram, \
    send_message, Nats

load_dotenv()
env: Env = get_data_env(Env)

logging.basicConfig(format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log = logging.getLogger("root")
log.setLevel(getattr(logging, env.log_level.upper()))

bots = [
    AsyncTeleBot(token)
    for token in env.TELEGRAM_BOT_TOKENS
]  # Bypass rate limit
bot = bots[0]
logging.info("count bots: %s", len(bots))

bots = cycle(bots)
nats: Nats | None = None
buffer: dict[int | str, Buffer] = {}


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

    if buffer[msg.message_thread_id].old_message_hash != text_hash or buffer[
        msg.message_thread_id].count >= env.repetition:
        buffer[msg.message_thread_id].old_message_hash = text_hash

        list_text = [buffer[msg.message_thread_id].string]
        buffer[msg.message_thread_id].count = 0

        if len(buffer[msg.message_thread_id].string) > 4000:
            list_text = split_string(buffer[msg.message_thread_id].string, 2000)

        for i in list_text:
            if await send_msg_telegram(next(bots), i, msg.message_thread_id, env.chat_id):
                buffer[msg.message_thread_id].string = ""

    await message.term()


async def main():
    global nats
    nats = Nats(await nats_connect(env))
    await nats.check_stream("tw", subjects=['tw.*', 'tw.*.*', 'tw.*.*.*'], max_age=60)

    await nats.js.subscribe("tw.tg.*", "telegram_bot", cb=message_handler_telegram)
    logging.info("nats js subscribe \"tw.tg.*\"")
    logging.info("bot is running")

    await bot.infinity_polling(logger_level=logging.DEBUG)


@bot.message_handler(content_types=["photo", "sticker", "sticker", "audio", "voice"])
async def echo_media(message: telebot.types.Message):
    if nats is None or message is None:
        return

    text = ""

    if message.reply_to_message is not None:
        reply = generate_message_reply(env.reply_string, env.text, message)
        text = f"say \"{reply[:255]}\";" if reply is not None else ""
    text += f"say \"{check_media(env, message)[:255]}\""

    await send_message(nats.js, text, message)


@bot.message_handler(content_types=["text"])
async def echo_text(message: telebot.types.Message):
    if nats is None or message is None or message.text.startswith("/"):
        return

    text = ""

    if message.reply_to_message is not None:
        reply = generate_message_reply(env.reply_string, env.text, message)
        text += f"say \"{reply[:255]}\";" if reply is not None else ""
    text += f"say \"{generate_message(env.text, message)[:255]}\""

    await send_message(nats.js, text, message)


if __name__ == '__main__':
    asyncio.run(main())
