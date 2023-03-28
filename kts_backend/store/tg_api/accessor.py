import random
import typing
from typing import Optional

from aiohttp import TCPConnector
from aiohttp.client import ClientSession

from kts_backend.store.base.base_accessor import BaseAccessor
from kts_backend.store.tg_api.dataclasses import Message, Update, UpdateObject
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
                    "allowed_updates": ["message"],
                    "timeout": 30,
                },
            )
        ) as resp:
            data = await resp.json()
            self.logger.info(data)
            # self.ts = data["ts"]
            raw_updates = data.get("result", [])
            updates = []

            for update in raw_updates:
                self.logger.info(update)
                if 'callback_query' in update:
                    updates.append(
                        Update(
                            update_id=update["update_id"],
                            object=UpdateObject(
                                chat_id=update["callback_query"]["message"]["chat"]["id"],
                                user_id=update["callback_query"]["from"]["id"],
                                body=update["callback_query"]["data"]

                            ),
                        )
                    )
                elif "my_chat_member" not in update:
                    updates.append(
                        Update(
                            update_id=update["update_id"],
                            object=UpdateObject(
                                chat_id=update["message"]["chat"]["id"],
                                user_id=update["message"]["from"]["id"],
                                body=update["message"]["text"]
                                if "text" in update["message"]
                                else "🧐",
                            ),
                        )
                    )
            if updates:
                self.offset = updates[-1].update_id + 1

            await self.app.store.bots_manager.handle_updates(updates)

    async def send_message(self, message: Message, keyboard: dict = None, remove_keyboard: bool=False) -> None:
        params={
            "chat_id": message.chat_id,
            "text": message.text
        }
        if keyboard:
            params['reply_markup']=keyboard
        if remove_keyboard:
            params['remove_keyboard']=True


        print(params)
        async with self.session.get(
            self._build_query(
                API_PATH + f"bot{self.app.config.bot.token}/",
                "sendMessage",
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




