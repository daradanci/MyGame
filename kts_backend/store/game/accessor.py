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
                amount_of_rounds=1,
                questions=[],
                rounds=[],
                status=new_game.status,
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
            return PlayerGameScoreDC(points=new_gamescore.points)

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
                    score=[PlayerGameScore(points=score.points)],
                )
                for (game, score, player) in players_raw
            ]
            # rounds_raw = await session.execute(
            #     select(Round, ThemeSet, Theme)
            #     .join(ThemeSet, Round.id == ThemeSet.round_id)
            #     .join(Theme, ThemeSet.theme_id == Theme.id)
            #     .where(Round.game_id == last_game.id)
            # )
            # rounds = [
            #     RoundDC(
            #         id=round.id,
            #         number=round.number,
            #         themes=[ThemeDC(id=theme.id,title=theme.title, questions=[]) ]
            #     )
            #     for (round, theme_set, theme) in rounds_raw
            # ]
            result_raw = await session.execute(
                select(Round).filter_by(game_id=last_game.id)
            )
            result = [res._mapping["Round"] for res in result_raw]

            rounds=[
                RoundDC(id=round.id, number=round.number,
                        themes=[
                            ThemeDC(id=theme.theme.id, title=theme.theme.title,
                                    questions=[
                                        QuestionDC(id=question.id, theme_id=question.theme_id, title=question.title,
                                                   points=question.points,
                                                   answers=[
                                                       AnswerDC(id=answer.id, title=answer.title, question_id=question.id)
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
                amount_of_rounds=int(last_game.amount_of_rounds),
                questions=last_game.questions,
                rounds=rounds,
            )

    async def get_chat_info(self, chat_id: int, tg_id: int):
        return await self.app.store.tg_api.get_chat_info(
            chat_id=chat_id, tg_id=tg_id
        )

    async def update_game(self, id: int,
                          chat_id: Optional[int] = None,
                          started_at: Optional[datetime] = None, finished_at: Optional[datetime] = None,
                          amount_of_rounds: Optional[int] = None,
                          status: Optional[str] = None
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
            if status:
                q = q.values(status=status)
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
