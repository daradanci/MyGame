from dataclasses import dataclass
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Boolean,
    DateTime,
    UniqueConstraint,
    ARRAY,
)
from sqlalchemy.orm import relationship
from kts_backend.store.database.sqlalchemy_base import db
from typing import Optional
import datetime


@dataclass
class GameDC:
    id: Optional[int]
    created_at: datetime
    chat_id: int
    players: Optional[list["PlayerDC"]]


@dataclass
class PlayerDC:
    tg_id: int
    name: str
    last_name: str
    score: Optional[list["GameScoreDC"]]


@dataclass
class GameScoreDC:
    points: Optional[int]
    # game: Optional['GameDC']
    # player: Optional['PlayerDC']


class GameModel(db):
    __tablename__ = "game"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    chat_id = Column(Integer, nullable=False)
    started_at = Column(DateTime, default=datetime.datetime.now, nullable=False)
    finished_at = Column(DateTime)

    players = relationship("GameScoreModel", backref="game")
    rounds = relationship("Round", backref="game")
    answered_questions = Column(ARRAY(Integer))

class PlayerModel(db):
    __tablename__ = "player"
    tg_id = Column(Integer, primary_key=True, unique=True)
    name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)

    score = relationship("GameScoreModel", backref="player")


class GameScoreModel(db):
    __tablename__ = "gamescore"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    points = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    incorrect_answers = Column(Integer, default=0)

    player_id = Column(Integer, ForeignKey("player.tg_id", ondelete="CASCADE"), nullable=False)
    game_id = Column(Integer, ForeignKey("game.id", ondelete="CASCADE"), nullable=False)


    __table_args__ = (
        UniqueConstraint("player_id", "game_id", name="_player_in_game_score"),
    )


class Round(db):
    __tablename__ = "round"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    game_id = Column(Integer, ForeignKey("game.id", ondelete="CASCADE"), nullable=False)
    number = Column(Integer, default=0)

    themes = relationship("ThemeSet", backref="round", cascade="all, delete")


class ThemeSet(db):
    __tablename__ = "themeset"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    game_id = Column(Integer, ForeignKey("game.id", ondelete="CASCADE"), nullable=False)
    theme_id = Column(Integer, ForeignKey("theme.id", ondelete="CASCADE"), nullable=False)


class Theme(db):
    __tablename__ = "theme"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    title = Column(String, nullable=False, unique=True)

    questions = relationship("Question", backref="theme", cascade="all, delete")
    sets = relationship("ThemeSet", backref="theme", cascade="all, delete")


class Question(db):
    __tablename__ = "question"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    title = Column(String, unique=True)
    answer = Column(String, nullable=False)
    theme_id = Column(Integer, ForeignKey("theme.id", ondelete="CASCADE"), nullable=False)


# class AnsweredQuestion(db):
#     __tablename__ = "answeredquestion"
#     id = Column(Integer, primary_key=True, index=True, unique=True)
#     game_id = Column(Integer, ForeignKey("game.id", ondelete="CASCADE"), nullable=False)
#     question_id = Column(Integer, ForeignKey("question.id", ondelete="CASCADE"), nullable=False)
#     player_id = Column(Integer, ForeignKey("player.id", ondelete="CASCADE"), nullable=False)
#     is_correct=Column(Boolean, default=False)








