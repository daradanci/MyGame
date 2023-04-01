from marshmallow import Schema, fields

from kts_backend.users.quiz.schemes import QuestionSchema
from kts_backend.web.schemes import OkResponseSchema




class GameScoreSchema(Schema):
    id = fields.Int()
    points = fields.Int(required=True)
    player_id = fields.Int()
    game_id = fields.Int()


class PlayerSchema(Schema):
    tg_id = fields.Int()
    name = fields.Str(required=True)
    last_name = fields.Str(required=True)
    score = fields.Nested(GameScoreSchema, many=True, required=False)


class GameSchema(Schema):
    id = fields.Int(attribute="id")
    created_at = fields.DateTime(required=False)
    chat_id = fields.Int(required=True)
    players = fields.Nested(PlayerSchema, many=True, required=True)
    amount_of_rounds=fields.Int()
    questions=fields.Nested(QuestionSchema, many=True)


