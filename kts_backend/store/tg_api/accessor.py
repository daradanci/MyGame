import random
import typing
from typing import Optional

from aiohttp import TCPConnector
from aiohttp.client import ClientSession

from kts_backend.store.base.base_accessor import BaseAccessor
from kts_backend.store.tg_api.dataclasses import Message, Update, UpdateObject, UserObject
from kts_backend.store.tg_api.poller import Poller

if typing.TYPE_CHECKING:
    from kts_backend.web.app import Application

API_PATH = f"https://api.telegram.org/"


class TgApiAccessor(BaseAccessor):
    def __init__(self, app: "Application", *args, **kwargs):
        super().__init__(app, *args, **kwargs)
        self.session: Optional[ClientSession] = None
        self.key: Optional[str] = None
        self.server: Optional[str] = None
        self.poller: Optional[Poller] = None
        self.offset: Optional[int] = None

    async def connect(self, app: "Application"):
        self.session = ClientSession(connector=TCPConnector(verify_ssl=False))
        self.poller = Poller(app.store)
        self.logger.info("start polling")
        await self.poller.start()

    async def disconnect(self, app: "Application"):
        if self.session:
            await self.session.close()
            self.session = None
        if self.poller:
            await self.poller.stop()

    @staticmethod
    def _build_query(host: str, method: str, params: dict) -> str:
        url = host + method + "?"
        # if "v" not in params:
        #     params["v"] = "5.131"

        url += "&".join([f"{k}={v}" for k, v in params.items()])
        return url

    async def poll(self):
        async with self.session.get(
                self._build_query(
                    host=API_PATH + f"bot{self.app.config.bot.token}/",
                    method="getUpdates",
                    params={
                        "offset": self.offset,
                        "allowed_updates": "messages",
                        "timeout": 30,
                    },
                )
        ) as resp:
            data = await resp.json()
            self.logger.info(data)
            raw_updates = data.get("result", [])
            updates = []

            for update in raw_updates:
                self.logger.info("!!!!!!!!!!!!!!!!!!!")
                self.logger.info(update)
                # self.logger.info()
                self.logger.info('!!!!!!!!!!!!!!!!!!!')

                if not update.get('message') and not update.get('callback_query'):
                    self.offset = update['update_id'] + 1
                    break

                if 'callback_query' in update:
                    updates.append(
                        Update(
                            update_id=update["update_id"],
                            object=UpdateObject(
                                message_id=update["callback_query"]["message"]["message_id"],
                                chat_id=update["callback_query"]["message"]["chat"]["id"],
                                user_id=update["callback_query"]["from"]["id"],
                                body=update["callback_query"]["data"],
                                user_info=UserObject(
                                    user_id=update["callback_query"]["from"]["id"],
                                    first_name=update["callback_query"]["from"]["first_name"],
                                    last_name=update["callback_query"]["from"]["last_name"]
                                    if "last_name" in update["callback_query"]["from"] else "",
                                    username=update["callback_query"]["from"]["username"]
                                    if "username" in update["callback_query"]["from"] else "",
                                )

                            ),
                        )
                    )
                if "message" in update and 'callback_query' not in update:
                        updates.append(
                            Update(
                                update_id=update["update_id"],
                                object=UpdateObject(
                                    message_id=update["message"]["message_id"],
                                    chat_id=update["message"]["chat"]["id"],
                                    user_id=update["message"]["from"]["id"],
                                    body=update["message"]["text"]
                                    if "text" in update["message"]
                                    else "🧐",
                                    user_info=UserObject(
                                        user_id=update["message"]["from"]["id"],
                                        first_name=update["message"]["from"]["first_name"],
                                        last_name=update["message"]["from"]["last_name"]
                                        if "last_name" in update["message"]["from"] else "",
                                        username=update["message"]["from"]["username"]
                                        if "username" in update["message"]["from"] else "",
                                    )
                                ),
                            )
                        )

            if updates:
                self.offset = updates[-1].update_id + 1

            await self.app.store.bots_manager.handle_updates(updates)

    async def send_message(self, message: Message, keyboard: dict = None, remove_keyboard: bool = False,
                           entities: str = None) -> Optional[int]:
        params = {
            "chat_id": message.chat_id,
            "text": message.text,
            "parse_mode": "Markdown"
        }
        if keyboard:
            params['reply_markup'] = keyboard
        if remove_keyboard:
            params['remove_keyboard'] = True
        if entities:
            params['entities'] = entities

        async with self.session.get(
                self._build_query(
                    API_PATH + f"bot{self.app.config.bot.token}/",
                    "sendMessage",
                    params=params,

                )
        ) as resp:
            data = await resp.json()
            self.logger.info(data)
            return int(data['result']['message_id']) if 'result' in data else None

    async def remove_keyboard(self, chat_id: int, message_id: int) -> None:
        params = {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": "",
        }
        async with self.session.get(
                self._build_query(
                    API_PATH + f"bot{self.app.config.bot.token}/",
                    "editMessageReplyMarkup",
                    params=params,
                )
        ) as resp:
            data = await resp.json()
            self.logger.info(data)

    async def get_chat_info(self, chat_id: int, tg_id: Optional[int]):
        if tg_id:
            async with self.session.get(
                    self._build_query(
                        API_PATH + f"bot{self.app.config.bot.token}/",
                        "getChatMember",
                        params={
                            "chat_id": chat_id,
                            "user_id": tg_id,
                        },
                    )
            ) as resp:
                data = await resp.json()
                self.logger.info(data)
            return data
        else:
            async with self.session.get(
                    self._build_query(
                        API_PATH + f"bot{self.app.config.bot.token}/",
                        "getChat",
                        params={
                            "chat_id": chat_id,
                        },
                    )
            ) as resp:
                data = await resp.json()
                self.logger.info(data)
            return data
