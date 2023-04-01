from marshmallow import Schema, fields
from kts_backend.web.schemes import OkResponseSchema


class ThemeSchema(Schema):
    id = fields.Int(attribute="id")
    title = fields.Str(attribute="title", required=True)


class AnswerSchema(Schema):
    title = fields.Str(required=True)


class QuestionSchema(Schema):
    id = fields.Int(attribute="id")
    title = fields.Str(attribute="title")
    theme_id = fields.Int(attribute="theme_id")
    points = fields.Int(attribute="points")
    answers = fields.Nested(AnswerSchema, many=True, attribute="answers")



class ThemeListSchema(Schema):
    data = fields.Nested(ThemeSchema, many=True)

class QuestionListSchema(Schema):
    data = fields.Nested(QuestionSchema, many=True)

class ThemeIdSchema(Schema):
    theme_id = fields.Int(required=False)




class ThemeAddSchema(Schema):
    title = fields.Str(required=True)


class ThemeListResponseSchema(OkResponseSchema):
    data = fields.Nested(ThemeListSchema)
