# from dataclasses import dataclass
# from sqlalchemy import Column, Integer, String, ForeignKey, Boolean
# from sqlalchemy.orm import relationship
# from kts_backend.store.database.sqlalchemy_base import db
# from typing import Optional
#
#
# @dataclass
# class Theme:
#     id: Optional[int]
#     title: str
#
#
# @dataclass
# class Question:
#     id: Optional[int]
#     title: str
#     theme_id: int
#     answers: list["Answer"]
#
#
# @dataclass
# class Answer:
#     title: str
#     is_correct: bool
#
#
# class ThemeModel(db):
#     __tablename__ = "themes"
#     id = Column(Integer, primary_key=True, index=True, unique=True)
#     title = Column(String, unique=True)
#     questions = relationship(
#         "QuestionModel", backref="themes", cascade="all, delete"
#     )
#
#
# class QuestionModel(db):
#     __tablename__ = "questions"
#     id = Column(Integer, primary_key=True, index=True, unique=True)
#     title = Column(String, unique=True)
#     theme_id = Column(
#         Integer, ForeignKey("themes.id", ondelete="CASCADE"), nullable=False
#     )
#     answers = relationship(
#         "AnswerModel",
#         backref="questions",
#         cascade="all, delete",
#         lazy="subquery",
#     )
#
#
# class AnswerModel(db):
#     __tablename__ = "answers"
#     id = Column(Integer, primary_key=True, index=True, unique=True)
#     title = Column(String)
#     is_correct = Column(Boolean)
#     question_id = Column(
#         Integer, ForeignKey("questions.id", ondelete="CASCADE")
#     )
