from typing import Optional
from aiohttp.web_exceptions import HTTPNotFound, HTTPConflict, HTTPBadRequest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker

from kts_backend.store.base.base_accessor import BaseAccessor
from kts_backend.users.game.models import *
from kts_backend.store.database.database import Database
from sqlalchemy import select, text, exc, delete


class QuizAccessor(BaseAccessor):
    async def create_theme(self, title: str) -> ThemeDC:
        async with self.app.database.session() as session:
            new_theme = Theme(title=str(title))
            session.add(new_theme)
            await session.commit()
            return ThemeDC(id=new_theme.id, title=new_theme.title, questions=[])

    async def get_theme_by_title(self, title: str) -> Optional[ThemeDC]:
        async with self.app.database.session() as session:
            result_raw = await session.execute(
                select(Theme).filter_by(title=title)
            )
            result = [res._mapping["Theme"] for res in result_raw]
            return (
                ThemeDC(id=result[0].id, title=result[0].title, questions=[])
                if len(result) > 0
                else None
            )

    async def get_theme_by_id(self, id_: int) -> Optional[ThemeDC]:
        async with self.app.database.session() as session:
            result_raw = await session.execute(
                select(Theme).filter_by(id=int(id_))
            )
            result = [res._mapping["Theme"] for res in result_raw]
            return (
                ThemeDC(id=result[0].id, title=result[0].title, questions=[])
                if len(result) > 0
                else None
            )

    async def list_themes(self) -> list[ThemeDC]:
        async with self.app.database.session() as session:
            result_raw = await session.execute(select(Theme))
            result = [res._mapping["Theme"] for res in result_raw]
            return [ThemeDC(id=theme.id, title=theme.title,questions=[]) for theme in result]

    async def create_answers(
            self, question_id: int, answers: list[AnswerDC]
    ) -> list[AnswerDC]:
        async with self.app.database.session() as session:
            session.add_all(
                [
                    Answer(
                        title=answer.title,
                        question_id=question_id,
                    )
                    for answer in answers
                ]
            )
            await session.commit()
        return [
            AnswerDC(id=answer.id, title=answer.title, question_id=answer.question_id)
            for answer in answers
        ]

    async def create_question(
            self, title: str, theme_id: int, answers: list[AnswerDC], points: int = 0
    ) -> QuestionDC:
        # if len(answers) < 2:
        #     raise HTTPBadRequest(reason=f"Слишком мало ответов")
        # if (
        #     len([answer for answer in answers if answer.is_correct]) == 0
        #     or len([answer for answer in answers if answer.is_correct]) > 1
        # ):
        #     raise HTTPBadRequest(reason=f"Должен быть 1 правильный ответ.")
        async with self.app.database.session() as session:
            new_question = Question(title=str(title), theme_id=theme_id, points=points)
            session.add(new_question)
            await session.commit()

            _answers = await self.create_answers(
                question_id=new_question.id,
                answers=[
                    AnswerDC(title=answer.title, question_id=new_question.id, id=None)
                    for answer in answers
                ],
            )

            return QuestionDC(
                id=int(new_question.id),
                title=new_question.title,
                theme_id=new_question.theme_id,
                points=new_question.points,
                answers=[
                    AnswerDC(title=answer.title, id=answer.id, question_id=answer.question_id)
                    for answer in answers
                ],
            )

    async def get_question_by_title(self, title: str) -> Optional[QuestionDC]:
        async with self.app.database.session() as session:
            res = await session.execute(
                select(Question)
                .join(Answer, Question.id == Answer.question_id)
                .where(Question.title == title)
            )
            question = res.scalars().first()

            return QuestionDC(
                id=int(question.id),
                title=question.title,
                theme_id=question.theme_id,
                points=question.points,
                answers=[
                    AnswerDC(title=answer.title, id=answer.id, question_id=answer.question_id)
                    for answer in question.answers
                ],
            )
    async def get_question_by_id(self, id: int) -> Optional[QuestionDC]:
        async with self.app.database.session() as session:
            res = await session.execute(
                select(Question)
                .join(Answer, Question.id == Answer.question_id)
                .where(Question.id == id)
            )
            question = res.scalars().first()

            return QuestionDC(
                id=int(question.id),
                title=question.title,
                theme_id=question.theme_id,
                points=question.points,
                answers=[
                    AnswerDC(title=answer.title, id=answer.id, question_id=answer.question_id)
                    for answer in question.answers
                ],
            )

    async def list_questions(
            self, theme_id: Optional[int] = None
    ) -> list[QuestionDC]:
        async with self.app.database.session() as session:
            if theme_id is not None:
                result_raw = await session.execute(
                    select(Question).filter_by(theme_id=int(theme_id))
                )
            else:
                result_raw = await session.execute(select(Question))
            result = [res._mapping["Question"] for res in result_raw]
            return [
                QuestionDC(
                    id=int(question.id),
                    title=question.title,
                    theme_id=question.theme_id,
                    points=question.points,
                    answers=[
                        AnswerDC(title=answer.title, id=answer.id, question_id=answer.question_id)
                        for answer in question.answers
                    ],
                )
                for question in result
            ]

    async def test(self):

        question = await self.create_question(
            title="Какие гуси жили у бабуси?",
            theme_id=151,
            answers=[
                Answer(
                    title="Белый и серый",
                ),
                Answer(
                    title="Чёрный и белый",
                ),
            ],
        )

        async with self.app.database.session() as session:
            res = await session.execute(select(Question))
            questions = res.scalars().all()

            res = await session.execute(select(Answer))
            db_answers = res.scalars().all()

            print("T1", questions)
            print("T2", db_answers)
        print("T3", len(db_answers))
