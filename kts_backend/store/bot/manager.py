import asyncio
import json
import typing
from logging import getLogger
import random

from kts_backend.store.tg_api.dataclasses import Message, Update
from kts_backend.users.game.enum_states import GameStatus as GS
from kts_backend.users.game.models import AnswerDC, RoundDC, PlayerDC, GameDC

if typing.TYPE_CHECKING:
    from kts_backend.web.app import Application


class BotManager:
    def __init__(self, app: "Application"):
        self.app = app
        self.bot = None
        self.logger = getLogger("handler")

    async def create_game(self, update: Update):
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

    async def join_game(self, update: Update):
        chat_info = await self.app.store.game.get_chat_info(chat_id=update.object.chat_id,
                                                            tg_id=update.object.user_id)
        # await self.app.store.tg_api.remove_keyboard(chat_id=update.object.chat_id,
        #                                             message_id=update.object.message_id)

        user_info = {
            'tg_id': chat_info['result']['user']['id'],
            'name': chat_info['result']['user']['first_name'],
            'last_name': chat_info['result']['user'].get('last_name', ''),
            'username': chat_info['result']['user'].get('username', '')
        }
        await self.app.store.game.register_player(player=user_info, chat_id=update.object.chat_id)

    async def setup_game(self, update: Update):
        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        if game_info.status!=GS.SETTING_ROUND:
            await self.app.store.tg_api.send_message(
                message=Message(
                    chat_id=update.object.chat_id,
                    text='Игра уже закончилась.',
                ))
            return None
        player = await self.app.store.game.check_if_playing(game_id=game_info.id,
                                                            tg_id=update.object.user_info.user_id)
        if player is None:
            return None
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

    async def setup_rounds(self, update: Update):
        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        player = await self.app.store.game.check_if_playing(game_id=game_info.id,
                                                            tg_id=update.object.user_info.user_id)
        if player is None:
            return None
        amount_of_rounds = int(update.object.body[len('/pick_rounds_'):])
        await self.app.store.game.update_game(id=game_info.id, status=GS.SETTING_QUESTIONS.value,
                                              amount_of_rounds=amount_of_rounds)
        await asyncio.gather(
            self.app.store.tg_api.send_message(
                Message(
                    chat_id=update.object.chat_id,
                    text=f'Выбрано: {amount_of_rounds} раунд(ов).',
                )
            ),
            self.app.store.tg_api.remove_keyboard(chat_id=update.object.chat_id,
                                                  message_id=update.object.message_id)
        )

    async def start_game(self, update: Update):
        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        if game_info.status in [GS.REGISTRATION.value, GS.SETTING_ROUND.value, GS.SETTING_QUESTIONS.value]:
            await self.app.store.game.update_game(id=game_info.id, status=GS.STARTED.value)
            await self.app.store.game.set_questions(chat_id=update.object.chat_id)
            game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
            rounds = game_info.rounds
            random_player = random.choices(game_info.players, k=1)[0]
            await asyncio.gather(
                self.print_questions(chat_id=update.object.chat_id, round=rounds[game_info.current_round - 1],
                                     player_answering=random_player),
                self.app.store.game.update_game(id=game_info.id, status=GS.PICKING_QUESTION.value,
                                                player_answering=random_player.tg_id),
            )
        else:
            return None

    async def pick_question(self, update: Update):
        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        # if game_info.player_answering != 0:
        if update.object.user_info.user_id != game_info.player_answering or game_info.status != GS.PICKING_QUESTION.value:
            return None
        player = await self.app.store.game.check_if_playing(game_id=game_info.id,
                                                            tg_id=update.object.user_info.user_id)
        if player is None:
            return None

        picked_question_id = int(update.object.body[len('/pick_question_'):])
        question = await self.app.store.quizzes.get_question_by_id(picked_question_id)
        await self.app.store.game.update_game(id=game_info.id, current_question=question.id)

        await self.app.store.tg_api.send_message(
            message=Message(
                chat_id=update.object.chat_id,
                text=question.title,
            ),
            keyboard=json.dumps({'inline_keyboard': [[
                {"text": "Ответить", "callback_data": f"/answer_question_{question.id}"},
            ]]},
            ))

    async def answer_question(self, update: Update):
        picked_question_id = int(update.object.body[len('/answer_question_'):])
        # question = await self.app.store.quizzes.get_question_by_id(picked_question_id)
        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        player = await self.app.store.game.check_if_playing(game_id=game_info.id,
                                                            tg_id=update.object.user_info.user_id)
        if player is None:
            return None
        await self.app.store.game.update_game(id=game_info.id, status=GS.ANSWERING_QUESTION.value,
                                              player_answering=player.tg_id, )

        await self.app.store.tg_api.send_message(
            message=Message(
                chat_id=update.object.chat_id,
                text=f'Отвечайте, {player.name}',
            )
        )
        await self.app.store.tg_api.remove_keyboard(chat_id=update.object.chat_id,
                                                    message_id=update.object.message_id)

    async def finish_game(self, update: Update):
        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        await asyncio.gather(
            self.app.store.game.update_game(id=game_info.id, status=GS.FINISHED.value),
            self.print_scoreboard(game_info=game_info),
            self.app.store.tg_api.send_message(
                Message(
                    chat_id=game_info.chat_id,
                    text=f"Игра окончена.",
                )
            )
        )

    async def scores(self, update: Update):
        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        await self.print_scoreboard(game_info=game_info)

    async def answer(self, update: Update):

        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        if game_info.status == GS.ANSWERING_QUESTION.value and game_info.player_answering:
            if update.object.user_info.user_id == game_info.player_answering:
                question = await self.app.store.quizzes.get_question_by_id(game_info.current_question)
                player = await self.app.store.game.check_if_playing(game_id=game_info.id,
                                                                    tg_id=update.object.user_info.user_id)
                if question is not None:
                    if await self.app.store.quizzes.match_answer(
                            given_answer=AnswerDC(id=None, question_id=None, title=update.object.body),
                            correct_answers=question.answers):
                        await self.app.store.tg_api.send_message(
                            Message(
                                chat_id=update.object.chat_id,
                                text=f"Правильный ответ!%0A Игрок {player.name} получает {question.points} очков.",
                            )
                        )

                        await self.app.store.game.update_player(game_id=game_info.id,
                                                                tg_id=player.tg_id,
                                                                correct_answers=player.score[
                                                                                    0].correct_answers + 1,
                                                                points=player.score[0].points + question.points)
                        await self.app.store.game.update_game(
                            id=game_info.id, player_answering=player.tg_id, status=GS.PICKING_QUESTION.value,
                            current_question=0, )
                    else:
                        await self.app.store.tg_api.send_message(
                            Message(
                                chat_id=update.object.chat_id,
                                text=f"Неверно.%0AПравильный ответ: {question.answers[0].title}",
                            )
                        )

                    await asyncio.gather(
                        self.app.store.game.update_player(
                            game_id=game_info.id,
                            tg_id=player.tg_id,
                            incorrect_answers=player.score[0].incorrect_answers + 1, ),
                        self.app.store.game.update_game(
                            id=game_info.id, status=GS.PICKING_QUESTION.value, current_question=0, ))

                    await self.print_questions(chat_id=update.object.chat_id,
                                               round=game_info.rounds[game_info.current_round - 1],
                                               player_answering=player),

    async def handle_updates(self, updates: list[Update]):
        for update in updates:
            if update.object.body == '/new_game':
                await self.create_game(update)
            elif update.object.body == '/join_game':
                await self.join_game(update)
            elif update.object.body == '/game_settings':
                await self.setup_game(update)
            elif update.object.body.startswith('/pick_rounds_'):
                await self.setup_rounds(update)
            elif update.object.body == '/start_game':
                await self.start_game(update)
            elif update.object.body.startswith('/pick_question_'):
                await self.pick_question(update)
            elif update.object.body.startswith('/answer_question_'):
                await self.answer_question(update)
            elif update.object.body=='/finish_game':
                await self.finish_game(update)
            elif update.object.body=='/scores':
                await self.scores(update)
            else:
                await self.answer(update)




    # async def game_round(self, updates: list[Update]):
    async def print_questions(self, chat_id: int, round: RoundDC, player_answering: PlayerDC):
        messages = []
        # messages.append(
        await    self.app.store.tg_api.send_message(
                message=Message(
                    chat_id=chat_id,
                    text=f'Раунд {round.number}.%0AСписок вопросов',
                )
            )
        # )
        for theme in round.themes:
            # messages.append(
            await   self.app.store.tg_api.send_message(
                    message=Message(
                        chat_id=chat_id,
                        text=theme.title,
                    ),
                    keyboard=json.dumps({'inline_keyboard': [[
                        {"text": question.points, "callback_data": f"/pick_question_{question.id}"}
                        for question in theme.questions
                    ]]},
                    ))
            await asyncio.sleep(1)
            # )
        # messages.append(
        await    self.app.store.tg_api.send_message(
                message=Message(
                    chat_id=chat_id,
                    text=f'Игрок {player_answering.name}, выбирайте вопрос.',
                )
            ),
        # )
        # await asyncio.gather(*messages)


    async def print_scoreboard(self, game_info:GameDC):
        players_info=''
        for player in game_info.players:
            players_info+=f'%0A{player.name} : {player.score[0].points} {player.score[0].correct_answers} {player.score[0].incorrect_answers}'
        await self.app.store.tg_api.send_message(
            Message(
                chat_id=game_info.chat_id,
                text=f"Текущие баллы."+players_info,
            )
        )
