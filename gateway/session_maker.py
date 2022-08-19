# The Derailed Gateway
#
# Copyright 2022 Derailed. All rights reserved.
#
# Sharing of any piece of code to any unauthorized third-party is not allowed.
from websockets.server import WebSocketServerProtocol

from gateway.session import Session


async def create_session(ws: WebSocketServerProtocol) -> None:
    session = Session(ws=ws)
    await session.run()
