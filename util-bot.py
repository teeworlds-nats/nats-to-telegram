import asyncio
import json
import logging

import telebot.types
from dotenv import load_dotenv
from nats.aio.msg import Msg as MsgNats
from telebot.async_telebot import AsyncTeleBot

from model import Env, MsgEvents
from util import nats_connect, get_data_env, Nats, search_custom_command, first_word_pattern

load_dotenv()
env: Env = get_data_env(Env)
commands = list(map(lambda x: search_custom_command(x.split(":")), env.custom))
commands_str = list(map(lambda x: x.slash_command, commands))

logging.basicConfig(format='%(asctime)s:%(levelname)s:%(name)s: %(message)s')
log = logging.getLogger("root")
log.setLevel(getattr(logging, env.log_level.upper()))

bot = AsyncTeleBot(env.util.tg_token)
nats: Nats | None = None

async def events_handler_telegram(message: MsgNats):
    """Takes a message from nats and sends it to telegram."""

    msg = MsgEvents(**json.loads(message.data.decode()))
    logging.debug("tw.events > %s", msg)
    await bot.send_message(
        env.util.chat_id,
        f"{msg.server_name}: `{msg.rcon}`",
        message_thread_id=env.util.logger_thread_id
    )

async def main():
    global nats
    nats = Nats(await nats_connect(env))

    await nats.js.subscribe("tw.events", "moderator_bot", cb=events_handler_telegram)
    logging.info("nats js subscribe \"tw.events\"")
    logging.info("bot is running")

    await bot.infinity_polling(logger_level=logging.DEBUG)


@bot.message_handler(content_types=["text"])
async def mod_echo_text(message: telebot.types.Message):
    if nats is None or message is None or not message.text.startswith("/") or env.util.chat_id == message.chat.id:
        return

    text = message.text.replace("/", "", 1)
    first_word = first_word_pattern.search(message.text).group(0)[1:]
    check_ignore = False
    if first_word in ["exec"]:
        if message.from_user.id not in env.admin_ids:
            return
        text = text[5:]
        check_ignore = True
    elif first_word in commands_str:
        chat_member = await bot.get_chat_member(message.chat.id, message.from_user.id)
        if not chat_member.custom_title in env.positions_custom_name:
            return
    else:
        return

    args = text.split(" ")
    command = next((i for i in commands if i.slash_command == first_word), None)
    if (command is not None and len(args) - 1 == command.count_args) or check_ignore:
        logging.debug("id: %s, sended to tw.econ.moderator: %s", message.from_user.id, args)
        await nats.js.publish(f"tw.econ.moderator", text.split(';')[0].encode())



if __name__ == '__main__':
    asyncio.run(main())
