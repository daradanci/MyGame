import asyncio
import datetime
import json
import operator
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

    async def start_timer(self, seconds, coroutine):
        await asyncio.sleep(seconds)
        await coroutine
    async def game_timer(self, seconds, game_id):
        await asyncio.sleep(seconds)
        game_info=await self.app.store.game.get_last_game(game_id=game_id)
        if game_info.status!=GS.FINISHED.value:
            await asyncio.gather(
                self.app.store.game.update_game(id=game_info.id, status=GS.FINISHED.value,
                                                finished_at=datetime.datetime.now()),
                self.app.store.tg_api.send_message(
                    Message(
                        chat_id=game_info.chat_id,
                        text=f"⏳ Время истекло: игра окончена. ❌",
                    )
                )
            )

    async def answer_timer(self, seconds, game_id, msg_id, quest_id):
        await asyncio.sleep(seconds)
        game_info=await self.app.store.game.get_last_game(game_id=game_id)
        await self.app.store.tg_api.remove_keyboard(chat_id=game_info.chat_id,
                                                    message_id=msg_id)
        if game_info.status == GS.FINISHED.value:
            return None
        if int(game_info.current_question)==quest_id:

            question = await self.app.store.quizzes.get_question_by_id(game_info.current_question)
            answered_questions = game_info.questions
            if question.id not in answered_questions:
                answered_questions.append(question.id)
            await self.app.store.tg_api.send_message(
                Message(
                    chat_id=game_info.chat_id,
                    text=f"⏳ Время истекло: следующий вопрос. ➡",
                )
            )
            await asyncio.sleep(1)
            player_old=await self.app.store.game.check_if_playing(game_id=game_id, tg_id=game_info.player_old)
            await asyncio.gather(
                self.app.store.game.update_game(
                    id=game_info.id, status=GS.PICKING_QUESTION.value, current_question=0,
                    questions=answered_questions
                ),
                self.print_questions(chat_id=game_info.chat_id,
                                     round=game_info.rounds[game_info.current_round - 1],
                                     player_answering=player_old,
                                     excluded_questions=answered_questions),
            )
            game_info = await self.app.store.game.get_last_game(game_id=game_id)
            questions_in_round = 0
            for theme in game_info.rounds[game_info.current_round - 1].themes:
                questions_in_round += len(theme.questions)
            if len(game_info.questions) >= questions_in_round:
                if game_info.current_round < len(game_info.rounds):
                    # next_round
                    await self.app.store.game.update_game(
                        id=game_info.id, current_question=0, current_round=game_info.current_round + 1, questions=[])
                    game_info = await self.app.store.game.get_last_game(game_info.chat_id)
                    await self.print_scoreboard(game_info=game_info)
                    await asyncio.sleep(4)
                    player_info = (await self.app.store.game.get_chat_info(
                        chat_id=game_info.chat_id, tg_id=game_info.player_old))['result'].get('user')
                    answering_player = PlayerDC(
                        tg_id=player_info['id'],
                        name=player_info['first_name'], last_name=player_info.get('last_name'),
                        username=player_info.get('username'), win_counts=0, score=[])

                    await self.print_questions(
                        chat_id=game_info.chat_id,
                        round=game_info.rounds[game_info.current_round - 1],
                        excluded_questions=[], player_answering=answering_player)
                else:
                    # finish
                    winner = None
                    if len(game_info.players) > 0:
                        winner = game_info.players[0]
                        if winner.score[0].points <= 0:
                            winner = None
                    if len(game_info.players) > 1 and winner is not None:
                        if winner.score[0].points == game_info.players[1].score[0].points:
                            winner = None
                        elif winner.score[0].points <= 0:
                            winner = None

                    if winner:
                        await self.app.store.tg_api.send_message(Message(
                            chat_id=game_info.chat_id,
                            text=f"👑Победитель: [{winner.name}](tg://user?id={winner.tg_id})👑"))
                        await self.app.store.game.update_player(tg_id=winner.tg_id, win_counts=winner.win_counts + 1)
                    else:
                        await self.app.store.tg_api.send_message(Message(
                            chat_id=game_info.object.chat_id,
                            text=f"✨Победила дружба!✨"))
                    await asyncio.gather(
                        self.app.store.game.update_game(id=game_info.id, status=GS.FINISHED.value,
                                                        finished_at=datetime.datetime.now()),
                        self.app.store.tg_api.send_message(
                            Message(
                                chat_id=game_info.chat_id,
                                text=f"Игра окончена.",
                            )
                        )
                    )




    async def create_game(self, update: Update):
        last_game = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        if last_game is not None:
            if last_game.status!=GS.FINISHED.value:
                await self.app.store.game.update_game(id=last_game.id, status=GS.FINISHED.value,
                                                      finished_at=datetime.datetime.now()),

        await self.app.store.game.start_game(chat_id=update.object.chat_id, players=[])
        message_id = await self.app.store.tg_api.send_message(
            Message(
                chat_id=update.object.chat_id,
                text='Начало новой игры.',
            ),
            keyboard=json.dumps({'inline_keyboard': [[
                {"text": "Присоединиться!", "callback_data": "/join_game"},
            ]]})
        )
        timer = asyncio.create_task(self.start_timer(
            seconds=10,
            coroutine=
            self.app.store.tg_api.remove_keyboard(
                chat_id=update.object.chat_id,
                message_id=message_id,
            )))
        # await timer

    async def join_game(self, update: Update):
        chat_info = await self.app.store.game.get_chat_info(chat_id=update.object.chat_id,
                                                            tg_id=update.object.user_id)

        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        if game_info.status != GS.REGISTRATION.value:
            return None
        user_info = {
            'tg_id': chat_info['result']['user']['id'],
            'name': chat_info['result']['user']['first_name'],
            'last_name': chat_info['result']['user'].get('last_name', ''),
            'username': chat_info['result']['user'].get('username', '')
        }
        await self.app.store.tg_api.send_message(
            Message(
                chat_id=update.object.chat_id,
                text=f'Пользователь [{update.object.user_info.first_name}](tg://user?id={update.object.user_info.user_id}) вступил в игру.',
            )
        )
        await self.app.store.game.register_player(player=user_info, chat_id=update.object.chat_id)

    async def setup_game(self, update: Update):
        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        if game_info.status not in [GS.SETTING_ROUND.value, GS.REGISTRATION.value]:
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
        if game_info.status != GS.SETTING_ROUND.value:
            return None
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
        if game_info is None:
            return None
        if game_info.status in [GS.REGISTRATION.value, GS.SETTING_ROUND.value, GS.SETTING_QUESTIONS.value]:
            if len(game_info.players) > 0:
                random_player = random.choices(game_info.players, k=1)[0]
            else:
                return None
            await asyncio.gather(
                self.app.store.game.update_game(id=game_info.id, status=GS.STARTED.value),
                self.app.store.game.set_questions(chat_id=update.object.chat_id)
            )
            game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
            rounds = game_info.rounds

            await asyncio.gather(
                self.print_questions(chat_id=update.object.chat_id, round=rounds[game_info.current_round - 1],
                                     player_answering=random_player, excluded_questions=game_info.questions),
                self.app.store.game.update_game(id=game_info.id, status=GS.PICKING_QUESTION.value,
                                                player_answering=0, player_old=random_player.tg_id),
            )
            asyncio.create_task(self.game_timer(len(game_info.rounds)*10*60, game_info.id))
        else:
            return None

    async def pick_question(self, update: Update):
        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)

        if update.object.user_info.user_id != game_info.player_old or \
                game_info.status != GS.PICKING_QUESTION.value or game_info.current_question!=0:
            return None

        player = await self.app.store.game.check_if_playing(game_id=game_info.id,
                                                            tg_id=update.object.user_info.user_id)
        if player is None:
            return None

        picked_question_id = int(update.object.body[len('/pick_question_'):])
        if picked_question_id in game_info.questions:
            return None

        question = await self.app.store.quizzes.get_question_by_id(picked_question_id)
        new_questions = game_info.questions
        # new_questions.append(question.id)
        await self.app.store.game.update_game(id=game_info.id, current_question=question.id, questions=new_questions,
                                              player_answering=0)

        sent_message_id=await self.app.store.tg_api.send_message(
            message=Message(
                chat_id=update.object.chat_id,
                text=question.title,
            ),
            keyboard=json.dumps({'inline_keyboard': [[
                {"text": "Ответить", "callback_data": f"/answer_question_{question.id}"},
            ]]},
            ))

        asyncio.create_task(self.answer_timer(
            seconds=40, game_id=game_info.id, msg_id=sent_message_id, quest_id=picked_question_id
        ))

    async def answer_question(self, update: Update):
        picked_question_id = int(update.object.body[len('/answer_question_'):])
        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        if game_info.current_question==0:
            return None
        if game_info.status != GS.PICKING_QUESTION.value:
            return None
        player = await self.app.store.game.check_if_playing(game_id=game_info.id,
                                                            tg_id=update.object.user_info.user_id)
        if player is None:
            return None
        await self.app.store.game.update_game(id=game_info.id, status=GS.ANSWERING_QUESTION.value,
                                              player_answering=player.tg_id, )

        await self.app.store.tg_api.send_message(
            message=Message(
                chat_id=update.object.chat_id,
                text=f'Отвечайте, [{player.name}](tg://user?id={player.tg_id})',
            )
        )



    async def finish_game(self, update: Update):
        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        await asyncio.gather(
            self.app.store.game.update_game(id=game_info.id, status=GS.FINISHED.value,
                                            finished_at=datetime.datetime.now()),
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
        if game_info is None:
            return None
        if game_info.status == GS.ANSWERING_QUESTION.value and game_info.player_answering and game_info.current_question!=0:
            if update.object.user_info.user_id == game_info.player_answering:
                question = await self.app.store.quizzes.get_question_by_id(game_info.current_question)
                player = await self.app.store.game.check_if_playing(game_id=game_info.id,
                                                                    tg_id=update.object.user_info.user_id)
                if question is not None:
                    if await self.app.store.quizzes.match_answer(
                            given_answer=AnswerDC(id=None, question_id=None, title=update.object.body),
                            correct_answers=question.answers):
                        await asyncio.gather(
                            self.app.store.tg_api.send_message(
                                Message(
                                    chat_id=update.object.chat_id,
                                    text=f"✅Правильный ответ!%0A Игрок [{player.name}](tg://user?id={player.tg_id}) получает {question.points} очков.",
                                )
                            ),
                            self.app.store.game.update_player(
                                game_id=game_info.id,
                                tg_id=player.tg_id,
                                correct_answers=player.score[0].correct_answers + 1,
                                points=player.score[0].points + question.points),
                            self.app.store.game.update_game(
                                id=game_info.id, player_old=game_info.player_answering,
                                current_question=0, player_answering=0,
                            ),
                        )
                        game_info = await self.app.store.game.get_last_game(chat_id=game_info.chat_id)
                        answered_questions = game_info.questions
                        if question.id not in answered_questions:
                            answered_questions.append(question.id)
                        player_info = (await self.app.store.game.get_chat_info(
                            chat_id=game_info.chat_id,
                            tg_id=game_info.player_old))['result'].get('user')
                        answering_player = PlayerDC(
                            tg_id=player_info['id'],
                            name=player_info['first_name'], last_name=player_info.get('last_name'),
                            username=player_info.get('username'), win_counts=0, score=[])

                        await self.app.store.game.update_game(
                            id=game_info.id, status=GS.PICKING_QUESTION.value, current_question=0,
                            questions=answered_questions
                        )
                        await self.print_questions(chat_id=update.object.chat_id,
                                                   round=game_info.rounds[game_info.current_round - 1],
                                                   player_answering=answering_player,
                                                   excluded_questions=game_info.questions),
                    else:
                        await asyncio.gather(
                            self.app.store.tg_api.send_message(
                                Message(
                                    chat_id=update.object.chat_id,
                                    text=f"❌Неверно. %0A Игрок [{player.name}](tg://user?id={player.tg_id}) теряет {question.points} очков.",
                                )
                            ),
                            self.app.store.game.update_player(
                                game_id=game_info.id,
                                tg_id=player.tg_id,
                                incorrect_answers=player.score[0].incorrect_answers + 1,
                                points=player.score[0].points - question.points),
                            self.app.store.game.update_game(
                                id=game_info.id, player_answering=0, status=GS.PICKING_QUESTION.value,
                                # current_question=0
                            ),
                        )


                    await self.win(update)

    async def handle_updates(self, updates: list[Update]):
        for update in updates:

            if update.object.body.startswith('/new_game'):
                await self.create_game(update)
            elif update.object.body.startswith('/scores'):
                await self.scores(update)
            elif update.object.body == '/join_game':
                await self.join_game(update)
            elif update.object.body.startswith('/game_settings'):
                await self.setup_game(update)
            elif update.object.body.startswith('/pick_rounds_'):
                await self.setup_rounds(update)
            elif update.object.body.startswith('/start_game'):
                await self.start_game(update)
            elif update.object.body.startswith('/pick_question_'):
                await self.pick_question(update)
            elif update.object.body.startswith('/answer_question_'):
                await self.answer_question(update)
            elif update.object.body.startswith('/finish_game'):
                await self.finish_game(update)

            else:
                await self.answer(update)

    async def win(self, update: Update):

        game_info = await self.app.store.game.get_last_game(chat_id=update.object.chat_id)
        if game_info is None:
            return None
        # if game_info.player_answering != update.object.user_info.user_id or \

        if len(game_info.questions) == 0:
            return None
        questions_in_round = 0
        for theme in game_info.rounds[game_info.current_round - 1].themes:
            questions_in_round += len(theme.questions)
        if len(game_info.questions) >= questions_in_round:
            if game_info.current_round < len(game_info.rounds):
                # next_round
                await self.app.store.game.update_game(
                    id=game_info.id, current_question=0, current_round=game_info.current_round + 1, questions=[])
                game_info = await self.app.store.game.get_last_game(game_info.chat_id)
                await self.print_scoreboard(game_info=game_info)
                await asyncio.sleep(4)
                player_info = (await self.app.store.game.get_chat_info(
                    chat_id=game_info.chat_id, tg_id=game_info.player_old))['result'].get('user')
                answering_player = PlayerDC(
                    tg_id=player_info['id'],
                    name=player_info['first_name'], last_name=player_info.get('last_name'),
                    username=player_info.get('username'), win_counts=0, score=[])

                await self.print_questions(
                    chat_id=game_info.chat_id,
                    round=game_info.rounds[game_info.current_round-1],
                    excluded_questions=[], player_answering=answering_player)
            else:
                # finish
                winner = None
                if len(game_info.players)>0:
                    winner=game_info.players[0]
                    if winner.score[0].points <= 0:
                        winner = None
                if len(game_info.players)>1 and winner is not None:
                    if winner.score[0].points == game_info.players[1].score[0].points:
                        winner=None
                    elif winner.score[0].points<=0:
                        winner=None

                if winner:
                    await self.app.store.tg_api.send_message(Message(
                        chat_id=update.object.chat_id,
                        text=f"👑Победитель: [{winner.name}](tg://user?id={winner.tg_id})👑"))
                    await self.app.store.game.update_player(tg_id=winner.tg_id, win_counts=winner.win_counts+1)
                    await self.finish_game(update)
                else:
                    await self.app.store.tg_api.send_message(Message(
                        chat_id=update.object.chat_id,
                        text=f"✨Победила дружба!✨"))
                    await self.finish_game(update)

    # async def game_round(self, updates: list[Update]):
    async def print_questions(self, chat_id: int, round: RoundDC, player_answering: PlayerDC,
                              excluded_questions: list[int]):
        messages = []
        # messages.append(
        await asyncio.sleep(4)

        await self.app.store.tg_api.send_message(
            message=Message(
                chat_id=chat_id,
                text=f'Раунд {round.number}.%0AСписок вопросов',
            )
        )
        # )
        await asyncio.sleep(1)

        for theme in round.themes:
            # messages.append(
            await asyncio.sleep(1)
            await self.app.store.tg_api.send_message(
                message=Message(
                    chat_id=chat_id,
                    text=theme.title,
                ),
                keyboard=json.dumps({'inline_keyboard': [[
                    {"text": question.points, "callback_data": f"/pick_question_{question.id}"}
                    for question in theme.questions
                    if question.id not in excluded_questions
                ]]},
                ))
            await asyncio.sleep(1)
            # )
        # messages.append(
        await self.app.store.tg_api.send_message(
            message=Message(
                chat_id=chat_id,
                text=f'Игрок [{player_answering.name}](tg://user?id={player_answering.tg_id}), выбирайте вопрос.',
            )
        ),
        # )
        # await asyncio.gather(*messages)

    async def print_scoreboard(self, game_info: GameDC):
        players_info = ''
        for player in game_info.players:
            players_info += f'%0A[{player.name}](tg://user?id={player.tg_id}) : {player.score[0].points} {player.score[0].correct_answers} {player.score[0].incorrect_answers}'

        await self.app.store.tg_api.send_message(
            Message(
                chat_id=game_info.chat_id,
                text=f"Таблица игровых баллов." + players_info,
            )
        )
