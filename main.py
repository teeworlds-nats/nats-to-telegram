import asyncio
import json
import logging
from itertools import cycle

import telebot.types
from nats.aio.msg import Msg as MsgNats
from telebot.util import split_string

from byfoxlib import Message
from byfoxlib.bot import Bot
from byfoxlib.model import Config, Msg, Path
from byfoxlib.util import nats_connect, get_config, generate_message_reply, generate_message, check_media, Nats

config: Config = get_config(Config)

logging.basicConfig(format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log = logging.getLogger("root")
log.setLevel(getattr(logging, config.log_level.upper()))


readers: dict[str, Path] = {}

for path in config.nats.paths:
    if isinstance(path.tokens, str):
        Bot(path.tokens)
    else:
        for token in path.tokens:
            Bot(token)

    path.tokens = cycle(path.tokens)
    readers[path.read] = path

readers_keys = list(readers.keys())
bots: dict[str, Bot] = Bot.get_tokens()
bot = list(bots.values())[0]

write_path = config.nats.write_path if config.nats.write_path is not None else ["tw.econ.write.{message_thread_id}"]

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

    if nats.server_name.get(msg.message_thread_id) is None:
        nats.server_name[msg.message_thread_id] = msg.server_name

    if not msg.args[0]:
        msg.args.pop(0)

    buffer_text[key] += (": ".join(msg.args) if reader.pattern is None else reader.pattern.format(msg.args)) + "\n"

    list_text = [buffer_text[key]] if len(buffer_text[key]) < 4000 else split_string(buffer_text[key], 2000)
    thread_id = msg.message_thread_id or reader.thread_id

    for text in list_text:
        bot_ = bots.get(next(reader.tokens))
        if await bot_.send_msg_telegram(
                text,
                reader.chat_id,
                thread_id
        ):
            buffer_text[key] = ""

    await message.ack()
    # await message.term()


async def main():
    global nats

    nats = Nats(await nats_connect(config))
    await nats.check_stream("tw", subjects=['tw.*', 'tw.*.*', 'tw.*.*.*'], max_msgs=1000)

    for _path in config.nats.paths:
        await nats.js.subscribe(_path.read, "telegram_bot", cb=message_handler_telegram)
    logging.info("nats js subscribe \"tw.tg.*\"")
    logging.info("bot is running")

    await bot.infinity_polling(
        logger_level=logging.DEBUG,
        allowed_updates=["message", "edited_message"]
    )


@bot.message_handler(content_types=["photo", "sticker", "sticker", "audio", "voice"])
async def echo_media(message: telebot.types.Message):
    if nats is None or message is None:
        return

    if config.nats.enable_process_messages:
        msg = Message()

        if message.reply_to_message is not None:
            reply = generate_message_reply(config.reply_string, config.text, message)
            msg + reply[:255] if reply is not None else ""
        msg + check_media(config, message)[:255]
        data = str(msg)
    else:
        data = json.dumps(message.__dict__)

    await nats.send_message(write_path, data, message)


@bot.message_handler(content_types=["text"])
async def echo_text(message: telebot.types.Message):
    if nats is None or message is None or message.text.startswith("/"):
        return

    if config.nats.enable_process_messages:
        msg = Message()

        if message.reply_to_message is not None:
            reply = generate_message_reply(config.reply_string, config.text, message)
            msg + reply[:255] if reply is not None else ""
        msg + generate_message(config.text, message)[:255]
        data = str(msg)
    else:
        data = json.dumps(message.__dict__)

    await nats.send_message(write_path, data, message)

@bot.edited_message_handler(content_types=["text"])
async def echo_edit_text(message: telebot.types.Message):
    if nats is None or message is None or message.text.startswith("/"):
        return

    if config.nats.enable_process_messages:
        string = config.edit_string.format(msg_id=message.id)
        text = generate_message(config.text, message)[:255]
        data = str(Message(f"{string} {text}"))
    else:
        data = json.dumps(message.__dict__)


    await nats.send_message(write_path, data, message)

if __name__ == '__main__':
    asyncio.run(main())
