import datetime
import random
from typing import Optional
from aiohttp.web_exceptions import HTTPNotFound, HTTPConflict, HTTPBadRequest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker, selectinload
from kts_backend.store.base.base_accessor import BaseAccessor
from kts_backend.users.game.models import *
from kts_backend.store.database.database import Database
from sqlalchemy import select, text, exc, delete, update, func
from datetime import datetime


class GameAccessor(BaseAccessor):
    async def start_game(self, chat_id: int, players) -> Optional[GameDC]:
        async with self.app.database.session() as session:
            new_game = Game(chat_id=int(chat_id))
            session.add(new_game)
            await session.commit()
            new_players = []
            for player in players:
                new_player = await self.check_player(player)
                new_players.append(
                    PlayerDC(
                        tg_id=new_player.tg_id,
                        name=new_player.name,
                        last_name=new_player.last_name,
                        username=new_player.username,
                        win_counts=new_player.win_counts,
                        score=[await self.bind_player(new_game, new_player)],

                    )
                )

            return GameDC(
                id=new_game.id,
                chat_id=new_game.chat_id,
                players=new_players,
                started_at=new_game.started_at,
                amount_of_rounds=new_game.amount_of_rounds,
                current_round=new_game.current_round,
                current_question=new_game.current_question,
                questions=[],
                rounds=[],
                status=new_game.status,
                player_answering=new_game.player_answering,
            )

    async def register_player(self, player, chat_id) -> Optional[PlayerDC]:
        try:
            new_player = await self.check_player(player)
            new_game = await self.get_last_game(int(chat_id))
            new_score = await self.bind_player(new_game=new_game, new_player=new_player)
        except IntegrityError as e:
            self.logger.error(e)
            return None

        return PlayerDC(
            tg_id=new_player.tg_id,
            name=new_player.name,
            last_name=new_player.last_name,
            username=new_player.username,
            win_counts=new_player.win_counts,
            score=[new_score],

        )

    async def bind_player(self, new_game, new_player) -> Optional[PlayerGameScoreDC]:
        async with self.app.database.session() as session:
            new_gamescore = PlayerGameScore(
                player_id=new_player.tg_id, game_id=new_game.id
            )
            session.add(new_gamescore)
            await session.commit()
            return PlayerGameScoreDC(points=new_gamescore.points, correct_answers=new_gamescore.correct_answers, incorrect_answers=new_gamescore.incorrect_answers)

    async def check_player(self, new_player) -> Optional[PlayerDC]:
        async with self.app.database.session() as session:
            result_raw = await session.execute(
                select(Player).filter_by(tg_id=new_player["tg_id"])
            )
            result = [res._mapping["Player"] for res in result_raw]
            return (
                result[0]
                if len(result) > 0
                else await self.add_player(new_player)
            )

    async def add_player(self, player) -> Optional[PlayerDC]:
        async with self.app.database.session() as session:
            new_player = Player(
                tg_id=player["tg_id"],
                name=player["name"],
                last_name=player["last_name"],
                username=player["username"],

            )
            session.add(new_player)
            await session.commit()
            return PlayerDC(
                tg_id=new_player.tg_id,
                name=new_player.name,
                last_name=new_player.last_name,
                username=new_player.username,
                win_counts=new_player.win_counts,
                score=[],
            )

    async def get_last_game(self, chat_id: int) -> Optional[GameDC]:
        async with self.app.database.session() as session:
            result_raw = await session.execute(
                select(Game)
                .filter_by(chat_id=int(chat_id))
                .order_by("started_at")
            )
            result = [res._mapping["Game"] for res in result_raw]

            if len(result) > 0:
                last_game = result[-1]
            else:
                raise HTTPNotFound(
                    reason=f"There are no games in chat #{chat_id}"
                )
            self.logger.info(last_game)
            players_raw = await session.execute(
                select(Game, PlayerGameScore, Player)
                .join(PlayerGameScore, Game.id == PlayerGameScore.game_id)
                .join(Player, Player.tg_id == PlayerGameScore.player_id)
                .where(Game.id == last_game.id)
            )
            players = [
                PlayerDC(
                    tg_id=player.tg_id,
                    name=player.name,
                    last_name=player.last_name,
                    username=player.username,
                    win_counts=player.win_counts,
                    score=[PlayerGameScore(points=score.points, correct_answers=score.correct_answers,  incorrect_answers=score.incorrect_answers)],
                )
                for (game, score, player) in players_raw
            ]
            result_raw = await session.execute(
                select(Round).filter_by(game_id=last_game.id)
            )
            result = [res._mapping["Round"] for res in result_raw]

            rounds = [
                RoundDC(id=round.id, number=round.number,
                        themes=[
                            ThemeDC(id=theme.theme.id, title=theme.theme.title,
                                    questions=[
                                        QuestionDC(id=question.id, theme_id=question.theme_id, title=question.title,
                                                   points=question.points,
                                                   answers=[
                                                       AnswerDC(id=answer.id, title=answer.title,
                                                                question_id=question.id)
                                                       for answer in question.answers
                                                   ])
                                        for question in theme.theme.questions
                                    ])
                            for theme in round.themes
                        ])
                for round in result
            ]
            return GameDC(
                id=int(last_game.id),
                started_at=last_game.started_at,
                chat_id=int(last_game.chat_id),
                status=last_game.status,
                players=players,
                questions=last_game.questions,
                amount_of_rounds=int(last_game.amount_of_rounds),
                current_round=int(last_game.current_round),
                current_question=int(last_game.current_question),
                rounds=rounds,
                player_answering=int(last_game.player_answering),
            )

    async def get_chat_info(self, chat_id: int, tg_id: int):
        return await self.app.store.tg_api.get_chat_info(
            chat_id=chat_id, tg_id=tg_id
        )

    async def update_game(self, id: int,
                          chat_id: Optional[int] = None,
                          started_at: Optional[datetime] = None, finished_at: Optional[datetime] = None,
                          amount_of_rounds: Optional[int] = None,
                          current_round: Optional[int] = None, current_question: Optional[int] = None,
                          status: Optional[str] = None, player_answering: Optional[int] = None,
                          ) -> Optional[GameDC]:
        async with self.app.database.session() as session:
            q = update(Game).where(Game.id == id)
            if chat_id:
                q = q.values(chat_id=chat_id)
            if started_at:
                q = q.values(started_at=started_at)
            if finished_at:
                q = q.values(finished_at=finished_at)
            if amount_of_rounds:
                q = q.values(amount_of_rounds=amount_of_rounds)
            if current_round:
                q = q.values(current_round=current_round)
            if current_question:
                q = q.values(current_question=current_question)
            if status:
                q = q.values(status=status)
            if player_answering:
                q = q.values(player_answering=player_answering)
            q.execution_options(synchronize_session="fetch")
            await session.execute(q)
            await session.commit()
        return None

    async def set_questions(self, chat_id: int, ):
        game_info = await self.get_last_game(chat_id=chat_id)
        self.logger.info(game_info)
        theme_list = await self.app.store.quizzes.list_themes()
        new_rounds = []
        async with self.app.database.session() as session:
            for r in range(1, game_info.amount_of_rounds + 1):
                try:
                    new_round = Round(game_id=game_info.id, number=r, )
                    session.add(new_round)
                    await session.commit()
                    new_rounds.append(RoundDC(id=new_round.id, number=new_round.number, themes=[]))
                except IntegrityError as e:
                    self.logger.error(e)
                    return None
        self.logger.info('@@@@@@@@@@@@@@@@@@')
        self.logger.info(new_rounds)
        self.logger.info('@@@@@@@@@@@@@@@@@@')

        async with self.app.database.session() as session:
            for new_round in new_rounds:
                random_themes = random.choices(theme_list, k=3)
                try:
                    session.add_all(
                        [
                            ThemeSet(round_id=new_round.id, theme_id=theme.id)
                            for theme in random_themes
                        ]
                    )
                    await session.commit()
                except IntegrityError as e:
                    self.logger.error(e)
                    return None

    async def check_if_playing(self, game_id: int, tg_id:int) -> Optional[PlayerDC]:
        async with self.app.database.session() as session:
            res = await session.execute(
                select(Player, PlayerGameScore)
                .join(PlayerGameScore, Player.tg_id == PlayerGameScore.player_id)
                .filter(Player.tg_id==tg_id)
            )
            # result = res.scalars().first()
            players = [
                PlayerDC(
                    tg_id=player.tg_id,
                    name=player.name,
                    last_name=player.last_name,
                    username=player.username,
                    win_counts=player.win_counts,
                    score=[PlayerGameScoreDC(points=score.points, correct_answers=score.correct_answers, incorrect_answers=score.incorrect_answers)],
                )
                for (player, score) in res
            ]
            self.logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            self.logger.info(players)
            self.logger.info('!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!')
            return players[0] if len(players) > 0 else None

    async def update_player(self, tg_id: int, username: Optional[str] = None, name:Optional[str] = None,
                            last_name: Optional[str] = None, win_counts: Optional[int] = None,
                            points: Optional[int] = None, correct_answers: Optional[int] = None,
                            incorrect_answers: Optional[int] = None,
                            ) -> None:
        async with self.app.database.session() as session:
            # q = update(Player).where(Player.tg_id==tg_id)
            q = update(Player).where(Player.tg_id == int(tg_id))
            q = q.values(tg_id=tg_id)

            if username:
                q = q.values(username=username)
            if name:
                q = q.values(name=name)
            if last_name:
                q = q.values(last_name=last_name)
            if win_counts:
                q = q.values(win_counts=win_counts)
            q.execution_options(synchronize_session="fetch")
            await session.execute(q)



            qq = update(PlayerGameScore).where(PlayerGameScore.player_id==int(tg_id))
            qq = qq.values(player_id=tg_id)
            if points:
                qq = qq.values(points=points)
            if correct_answers:
                qq = qq.values(correct_answers=correct_answers)
            if incorrect_answers:
                qq = qq.values(incorrect_answers=incorrect_answers)
            qq.execution_options(synchronize_session="fetch")
            await session.execute(qq)

            await session.commit()


