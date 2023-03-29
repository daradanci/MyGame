from dataclasses import dataclass
from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Boolean,
    DateTime,
    UniqueConstraint,
    ARRAY, BigInteger,
)
from sqlalchemy.orm import relationship
from kts_backend.store.database.sqlalchemy_base import db
from typing import Optional
import datetime
from .enum_states import GameStatus as GS


@dataclass
class GameDC:
    id: Optional[int]
    started_at: datetime
    # finished_at: Optional[datetime]
    chat_id: int
    status: Optional[str]
    players: Optional[list["PlayerDC"]]
    rounds: Optional[list["RoundDC"]]
    questions: Optional[list[int]]
    amount_of_rounds: Optional[int]
    current_round: Optional[int]
    current_question: Optional[int]


@dataclass
class PlayerDC:
    tg_id: int
    name: str
    last_name: str
    username: str
    win_counts:int
    score: Optional[list["PlayerGameScoreDC"]]


@dataclass
class PlayerGameScoreDC:
    points: Optional[int]
    # game: Optional['GameDC']
    # player: Optional['PlayerDC']
@dataclass
class RoundDC:
    id: Optional[int]
    number: int
    themes: Optional[list["ThemeDC"]]


@dataclass
class ThemeDC:
    id: Optional[int]
    title: str
    questions: Optional[list["QuestionDC"]]


@dataclass
class QuestionDC:
    id: Optional[int]
    theme_id: Optional[int]
    title: str
    points: int
    answers: Optional[list["AnswerDC"]]

@dataclass
class AnswerDC:
    id: Optional[int]
    question_id:Optional[int]
    title: str


class Game(db):
    __tablename__ = "game"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    chat_id = Column(Integer, nullable=False)
    started_at = Column(DateTime, default=datetime.datetime.now, nullable=False)
    finished_at = Column(DateTime)
    amount_of_rounds = Column(Integer, default=1)
    status = Column(String, default=GS.REGISTRATION.value)
    player_answering=Column(BigInteger, default=0)
    current_round=Column(Integer, default=1)
    current_question=Column(Integer, default=0)
    players = relationship("PlayerGameScore", backref="game", lazy="subquery")
    rounds = relationship("Round", backref="game", lazy="subquery")
    questions = Column(ARRAY(Integer),default=[])


class Player(db):
    __tablename__ = "player"
    tg_id = Column(BigInteger, primary_key=True, unique=True)
    username = Column(String, nullable=False)
    name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    win_counts=Column(Integer, default=0)
    score = relationship("PlayerGameScore", backref="player",lazy="subquery")


class PlayerGameScore(db):
    __tablename__ = "gamescore"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    points = Column(Integer, default=0)
    correct_answers = Column(Integer, default=0)
    incorrect_answers = Column(Integer, default=0)

    player_id = Column(
        BigInteger, ForeignKey("player.tg_id", ondelete="CASCADE"), nullable=False
    )
    game_id = Column(
        Integer, ForeignKey("game.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("player_id", "game_id", name="_player_in_game_score"),
    )


class Round(db):
    __tablename__ = "round"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    game_id = Column(
        Integer, ForeignKey("game.id", ondelete="CASCADE"), nullable=False
    )
    number = Column(Integer, default=0)

    themes = relationship("ThemeSet", backref="round", cascade="all, delete", lazy="subquery")


class ThemeSet(db):
    __tablename__ = "themeset"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    round_id = Column(
        Integer, ForeignKey("round.id", ondelete="CASCADE"), nullable=False
    )
    theme_id = Column(
        Integer, ForeignKey("theme.id", ondelete="CASCADE"), nullable=False
    )
    theme = relationship("Theme", back_populates="sets", lazy="subquery")


class Theme(db):
    __tablename__ = "theme"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    title = Column(String, nullable=False, unique=True)

    questions = relationship("Question", backref="theme", cascade="all, delete",lazy="subquery")
    sets = relationship("ThemeSet", back_populates="theme", cascade="all, delete",lazy="subquery")


class Question(db):
    __tablename__ = "question"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    title = Column(String, unique=True)
    points = Column(Integer, default=0)
    theme_id = Column(
        Integer, ForeignKey("theme.id", ondelete="CASCADE"), nullable=False
    )
    answers = relationship("Answer", backref="question", cascade="all, delete", lazy="subquery",)


class Answer(db):
    __tablename__ = "answer"
    id = Column(Integer, primary_key=True, index=True, unique=True)
    title = Column(String)
    question_id = Column(
        Integer, ForeignKey("question.id", ondelete="CASCADE")
    )