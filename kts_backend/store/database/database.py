from typing import Optional, TYPE_CHECKING, Callable

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base, Session, sessionmaker
from sqlalchemy import select, text, exc

# from app.quiz.models import Theme, ThemeModel
# from kts_backend.store.database import db
from kts_backend.store.database.sqlalchemy_base import db

if TYPE_CHECKING:
    from kts_backend.web.app import Application


class Database:
    def __init__(self, app: "Application"):
        self.app = app
        self._engine: Optional[AsyncEngine] = None
        self._db: Optional[declarative_base] = None
        self.session: Optional[Callable[[], AsyncSession]] = None

    async def connect(self, *_: list, **__: dict) -> None:
        self._db = db
        # echo=True,future=True
        self._engine = create_async_engine(
            "postgresql+asyncpg://kts_user:kts_pass@localhost/MyGame"
        )
        print("CONNECTED to database successfully")
        self.session = sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )



    async def disconnect(self, *_: list, **__: dict) -> None:
        # self.session.expunge_all()
        if self._engine:
            await self._engine.dispose()
