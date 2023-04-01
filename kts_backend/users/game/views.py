import json

from aiohttp.web_exceptions import (
    HTTPNotFound,
    HTTPUnauthorized,
    HTTPForbidden,
    HTTPConflict,
    HTTPBadRequest,
)
from aiohttp_apispec import response_schema, docs, request_schema
from sqlalchemy.orm import class_mapper

from kts_backend.users.game.models import *
from kts_backend.users.game.schemes import *
from kts_backend.web.app import View
from kts_backend.web.schemes import OkResponseSchema
from kts_backend.web.utils import json_response
from kts_backend.web.mixins import AuthRequiredMixin


class GetGameInfoView( View):
    @docs(
        tags=["web"],
        summary="Game info",
        description="Get last game info with chat_id",
    )
    @response_schema(OkResponseSchema)
    async def get(self):
        game_info = await self.store.game.get_last_game(
            chat_id=self.request.rel_url.query["chat_id"]
        )
        print(game_info)
        return json_response(
            data={
                "id": game_info.id,
                "chat_id": game_info.chat_id,
                "started_at": str(game_info.started_at),
                "status":game_info.status,
                "players": [
                    {
                        "tg_id": player.tg_id,
                        "name": player.name,
                        "last_name": player.last_name,
                        "username":player.username,
                        "win_counts":player.win_counts,
                        "score": [{"points":score.points, "correct_answers":score.correct_answers,"incorrect_answers":score.incorrect_answers } for score in player.score],
                    }
                    for player in game_info.players
                ],
                "player_answering": game_info.player_answering,
                "player_old": game_info.player_old,
                "amount_of_rounds": game_info.amount_of_rounds,
                "current_round": game_info.current_round,
                "current_question": game_info.current_question,
                "questions": game_info.questions,
                "rounds": [
                    {
                        "id": round.id,
                        "number":round.number,
                        "themes":[
                            {
                                "id":theme.id,
                                "title":theme.title,
                                "questions":[
                                    {
                                        "id":question.id,
                                        "theme_id":question.theme_id,
                                        "title":question.title,
                                        "points":question.points,
                                        "answers":[
                                            {
                                                "id":answer.id,
                                                "question_id":answer.question_id,
                                                "title":answer.title,
                                            }
                                            for answer in question.answers
                                        ]
                                    }
                                    for question in theme.questions
                                ]
                            }
                            for theme in round.themes
                        ]
                    }
                    for round in game_info.rounds
                ]
            }
        )


class GetChatInfoView(AuthRequiredMixin, View):
    @docs(
        tags=["web"],
        summary="Get chat info",
        description="Get chat info using chat_id and tg_id",
    )
    @response_schema(OkResponseSchema)
    async def get(self):
        chat_info = await self.store.game.get_chat_info(
            chat_id=self.request.rel_url.query["chat_id"],
            tg_id=self.request.rel_url.query["user_id"]
            if "user_id" in self.request.rel_url.query
            else None,
        )
        return json_response(chat_info["result"])


class StartGameView(AuthRequiredMixin, View):
    @docs(
        tags=["web"],
        summary="Start game",
        description="Start new game with chat_id",
    )
    @request_schema(GameSchema)
    @response_schema(OkResponseSchema)
    async def post(self):
        new_game = await self.store.game.start_game(
            chat_id=self.data["chat_id"], players=self.data["players"]
        )

        return json_response(
            data={
                "id": new_game.id,
                "chat_id": new_game.chat_id,
                "started_at": str(new_game.started_at),
                "status": new_game.status,
                "players": [
                    {
                        "tg_id": player.tg_id,
                        "name": player.name,
                        "last_name": player.last_name,
                        "username": player.username,
                        "win_counts": player.win_counts,
                        "score": [score.points for score in player.score],
                    }
                    for player in new_game.players
                ],
                "amount_of_rounds":new_game.amount_of_rounds,
                "current_round":new_game.current_round,
                "questions":new_game.questions,
                "rounds": new_game.rounds,
            }
        )
