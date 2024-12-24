import logging

from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException

log = logging.getLogger(__name__)


class Bot(AsyncTeleBot):
    def __init__(self, token: str, *args, **kwargs):
        super().__init__(token, *args, **kwargs)
        g = globals()
        if g.get("bots") is None:
            g["bots"] = {}

        g["bots"][token] = self

    async def send_msg_telegram(self, text: str, chat_id: int | str, thread_id: int | None) -> bool:
        try:
            await self.send_message(chat_id, text, message_thread_id=thread_id)
        except ApiTelegramException as err:
            logging.debug("ApiTelegramException occurred: %s", err)
        else:
            return True
        return False

    @staticmethod
    def get_tokens() -> dict[str, "Bot"] | None:
        bots = globals().get("bots")
        log.info("count bots: %s", len(bots))
        return bots
