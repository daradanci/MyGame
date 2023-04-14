import typing

from kts_backend.users.game.views import (
    GetGameInfoView,
    StartGameView,
    GetChatInfoView,
    GetGamesListView
)

if typing.TYPE_CHECKING:
    from kts_backend.web.app import Application


def setup_routes(app: "Application"):
    app.router.add_view("/game.info", GetGameInfoView)
    app.router.add_view("/game.list", GetGamesListView)
    app.router.add_view("/game.start", StartGameView)
    app.router.add_view("/chat.info", GetChatInfoView)
