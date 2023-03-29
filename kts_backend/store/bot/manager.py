import json
import typing
from logging import getLogger

from kts_backend.store.tg_api.dataclasses import Message, Update
from kts_backend.users.game.enum_states import GameStatus as GS

if typing.TYPE_CHECKING:
    from kts_backend.web.app import Application


class BotManager:
    def __init__(self, app: "Application"):
        self.app = app
        self.bot = None
        self.logger = getLogger("handler")

    async def handle_updates(self, updates: list[Update]):
        for update in updates:
            if update.object.body == '/new_game':
                await self.app.store.game.start_game(chat_id=update.object.chat_id, players=[])

                await self.app.store.tg_api.send_message(
                    Message(
                        chat_id=update.object.chat_id,
                        text='Начало новой игры.',
                    ),
                    keyboard=json.dumps({'inline_keyboard': [[
                        {"text": "Присоединиться!", "callback_data": "/join_game"},
                    ]]})
                )
            elif update.object.body == '/join_game':
                chat_info = await self.app.store.game.get_chat_info(chat_id=update.object.chat_id,
                                                                    tg_id=update.object.user_id)
                await self.app.store.tg_api.remove_keyboard(chat_id=update.object.chat_id, message_id=update.object.message_id)

                user_info = {
                    'tg_id': chat_info['result']['user']['id'],
                    'name': chat_info['result']['user']['first_name'],
                    'last_name': '',
                    'username': ''
                }
                if 'last_name' in chat_info['result']['user']:
                    user_info['last_name'] = chat_info['result']['user']['last_name']
                if 'username' in chat_info['result']['user']:
                    user_info['username'] = chat_info['result']['user']['username']
                await self.app.store.game.register_player(player=user_info, chat_id=update.object.chat_id)
            elif update.object.body == '/game_settings':
                game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
                await self.app.store.tg_api.send_message(
                    message=Message(
                        chat_id=update.object.chat_id,
                        text='Выберите количество раундов',
                    ),
                    keyboard=json.dumps({'inline_keyboard': [[
                        {"text": "1", "callback_data": "/pick_rounds_1"},
                        {"text": "2", "callback_data": "/pick_rounds_2"},
                        {"text": "3", "callback_data": "/pick_rounds_3"}
                    ]]},
                    ))
                await self.app.store.game.update_game(id=game_info.id, status=GS.SETTING_ROUND.value)
            elif update.object.body.startswith('/pick_rounds_'):
                amount_of_rounds=int(update.object.body[len('/pick_rounds_'):])
                game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
                await self.app.store.game.update_game(id=game_info.id, status=GS.SETTING_QUESTIONS.value,
                                                      amount_of_rounds=amount_of_rounds)
                await self.app.store.tg_api.send_message(
                    Message(
                        chat_id=update.object.chat_id,
                        text=f'Выбрано: {amount_of_rounds} раунд(ов).',
                    )
                )
                await self.app.store.tg_api.remove_keyboard(chat_id=update.object.chat_id, message_id=update.object.message_id)

            elif update.object.body == '/start_game':
                game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)

                await self.app.store.game.update_game(id=game_info.id, status=GS.STARTED.value)
                await self.app.store.game.set_questions(chat_id=update.object.chat_id)
                game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
                rounds=game_info.rounds
                await self.app.store.tg_api.send_message(
                    message=Message(
                        chat_id=update.object.chat_id,
                        text='Раунд 1.\n Список вопросов',
                    ))
                for theme in rounds[game_info.current_round-1].themes:
                    await self.app.store.tg_api.send_message(
                        message=Message(
                            chat_id=update.object.chat_id,
                            text=theme.title,
                        ),
                        keyboard=json.dumps({'inline_keyboard': [[
                            {"text": question.points, "callback_data": f"/pick_question_{question.id}"}
                            for question in theme.questions
                        ]]},
                        ))
            elif update.object.body.startswith('/pick_question_'):
                picked_question_id=int(update.object.body[len('/pick_question_'):])
                question=await self.app.store.quizzes.get_question_by_id(picked_question_id)
                await self.app.store.tg_api.send_message(
                    message=Message(
                        chat_id=update.object.chat_id,
                        text=question.title,
                    ),
                    keyboard=json.dumps({'inline_keyboard': [[
                        {"text": "Ответить", "callback_data": f"/answer_question_{question.id}"},
                    ]]},
                    ))
            elif update.object.body.startswith('/answer_question_'):
                picked_question_id = int(update.object.body[len('/answer_question_'):])
                question = await self.app.store.quizzes.get_question_by_id(picked_question_id)
                game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
                player=await self.app.store.game.check_if_playing(game_id=game_info.id)
                if player is None:
                    return None

                await self.app.store.tg_api.send_message(
                    message=Message(
                        chat_id=update.object.chat_id,
                        text=f'Отвечайте, {player.name}',
                    )
                )
                await self.app.store.tg_api.remove_keyboard(chat_id=update.object.chat_id, message_id=update.object.message_id)

            else:

                # await self.app.store.tg_api.send_message(
                #     Message(
                #         chat_id=update.object.chat_id,
                #         text=update.object.body,
                #     )
                # )
                pass

    # async def game_round(self, updates: list[Update]):

