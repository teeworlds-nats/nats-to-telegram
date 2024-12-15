import asyncio
import json
import logging
from itertools import cycle

import telebot.types
from dotenv import load_dotenv
from nats.aio.msg import Msg as MsgNats
from telebot.async_telebot import AsyncTeleBot
from telebot.util import split_string

from emojies import replace_from_str
from model import Env, Msg, Path
from util import nats_connect, get_data_env, generate_message_reply, generate_message, check_media, send_msg_telegram, \
    send_message, Nats

load_dotenv()
env: Env = get_data_env(Env)

logging.basicConfig(format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log = logging.getLogger("root")
log.setLevel(getattr(logging, env.log_level.upper()))


readers: dict[str, Path] = {}
tokens: list[str] = []

for path in env.nats.paths:
    if isinstance(path.tokens, list):
        tokens.extend(path.tokens)
    else:
        tokens.append(path.tokens)

    path.tokens = cycle(path.tokens)
    readers[path.read] = path

readers_keys = list(readers.keys())
bots: dict[str, AsyncTeleBot] = { token: AsyncTeleBot(token) for token in tokens }
bot = list(bots.values())[0]
logging.info("count bots: %s", len(bots))

write_path = env.nats.write_path if env.nats.write_path is not None else ["tw.econ.write.{message_thread_id}"]

nats: Nats | None = None
buffer_text = {}


async def message_handler_telegram(message: MsgNats):
    """Takes a message from nats and sends it to telegram."""
    await message.in_progress()

    msg = Msg(**json.loads(message.data.decode()))
    key = msg.message_thread_id or msg.server_name
    logging.debug("%s > %s", message.subject, msg.args)

    rd_path = next((i for i in readers_keys if any(sub1 == sub2 or sub2 == "*" for sub1, sub2 in zip(message.subject.split("."), i.split(".")))), "")

    if not rd_path:
        return await message.ack()

    reader = readers.get(rd_path)
    if reader is None:
        return await message.ack()

    if buffer_text.get(key) is None:
        buffer_text[key] = ""

    if not msg.args[0]:
        msg.args.pop(0)

    buffer_text[key] += ": ".join(msg.args) if reader.pattern is None else reader.pattern.format(msg.args)

    list_text = [buffer_text[key]] if len(buffer_text[key]) < 4000 else split_string(buffer_text[key], 2000)
    thread_id = msg.message_thread_id or reader.thread_id

    for text in list_text:
        if await send_msg_telegram(
                bots.get(next(reader.tokens)),
                text.replace("{{message_thread_id}}", thread_id),
                reader.chat_id,
                thread_id
        ):
            buffer_text[key] = ""

    await message.ack()
    # await message.term()


async def main():
    global nats

    nats = Nats(await nats_connect(env))
    await nats.check_stream("tw", subjects=['tw.*', 'tw.*.*', 'tw.*.*.*'], max_msgs=1000)

    await nats.js.subscribe("tw.tg.*", "telegram_bot", cb=message_handler_telegram)
    logging.info("nats js subscribe \"tw.tg.*\"")
    logging.info("bot is running")

    await bot.infinity_polling(logger_level=logging.DEBUG, allowed_updates=["message", "edited_message"])


@bot.message_handler(content_types=["photo", "sticker", "sticker", "audio", "voice"])
async def echo_media(message: telebot.types.Message):
    if nats is None or message is None:
        return


    if env.nats.enable_process_messages:
        text = ""
        if message.reply_to_message is not None:
            reply = generate_message_reply(env.reply_string, env.text, message)
            text = f"say \"{reply[:255]}\";" if reply is not None else ""
        text += f"say \"{check_media(env, message)[:255]}\""
    else:
        text = json.dumps(message.__dict__)

    await send_message(write_path, nats.js, text, message)


@bot.message_handler(content_types=["text"])
async def echo_text(message: telebot.types.Message):
    if nats is None or message is None or message.text.startswith("/"):
        return

    if env.nats.enable_process_messages:
        text = ""
        if message.reply_to_message is not None:
            reply = generate_message_reply(env.reply_string, env.text, message)
            text += f"say \"{reply[:255]}\";" if reply is not None else ""
        text += f"say \"{generate_message(env.text, message)[:255]}\""
    else:
        text = json.dumps(message.__dict__)

    await send_message(write_path, nats.js, text, message)

@bot.edited_message_handler(content_types=["text"])
async def echo_edit_text(message: telebot.types.Message):
    if nats is None or message is None or message.text.startswith("/"):
        return

    text = f"say \"{env.edit_string.format(msg_id=message.id)} {generate_message(env.text, message)[:255]}\"" \
        if env.nats.enable_process_messages \
        else json.dumps(message.__dict__)

    await send_message(
        write_path,
        nats.js,
        text,
        message
    )

if __name__ == '__main__':
    asyncio.run(main())
