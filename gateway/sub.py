# The Derailed Gateway
#
# Copyright 2022 Derailed. All rights reserved.
#
# Sharing of any piece of code to any unauthorized third-party is not allowed.
from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING

import msgspec
from aiokafka import AIOKafkaConsumer
from websockets.legacy.protocol import broadcast

from gateway.database import Message

if TYPE_CHECKING:
    from gateway.session import Session


# This class implements the *sub* part of pubsub.
class Subscriptor:
    def __init__(self) -> None:
        self.sessions: dict[str, Session] = {}
        self.user_id_sorted_sessions: dict[str, set[str]] = {}
        self.guilds: dict[str, set[str]] = {}
        self.is_ready: bool = False

    async def make_ready(self) -> None:
        if not self.is_ready:
            self.consumer = AIOKafkaConsumer(bootstrap_servers=os.getenv('KAFKA_URI'))
            await self.consumer.start()
            asyncio.create_task(self.iterate_events())

    async def iterate_events(self) -> None:
        self.consumer.subscribe(['user', 'security'])
        async for msg in self.consumer:
            message = msgspec.msgpack.decode(msg, type=Message)

            if message.name == 'USER_DISCONNECT':
                user = self.user_id_sorted_sessions.get(message.user_id)

                if user is None:
                    continue

                sessions = [self.sessions.get(session_id) for session_id in user]

                for session in sessions:
                    await session._disconnect(
                        'Forceful Disconnection, could be a token reset or account deletion.'
                    )

            if message.user_id:
                user = self.user_id_sorted_sessions.get(message.user_id)

                if user is None:
                    continue

                websockets = []

                for session_id in user:
                    session = self.sessions.get(session_id)
                    websockets.append(session.ws)

                data = {
                    'op': 0,
                    't': message.name,
                    'd': message.data,
                }

                broadcast(websockets=websockets, message=data)

    def subscribe(self, session: Session) -> None:
        self.sessions[session.session_id] = session
        if self.user_id_sorted_sessions.get(session.user.id) is None:
            self.user_id_sorted_sessions[session.user.id] = {session.session_id}
        else:
            self.user_id_sorted_sessions[session.user.id].add(session.session_id)

    def unsubscribe(self, session: Session) -> None:
        self.sessions.pop(session.session_id)
        user = self.user_id_sorted_sessions[session.user.id]
        user.remove(session.session_id)
        if len(user) == 0:
            self.user_id_sorted_sessions.pop(session.user.id)
        else:
            self.user_id_sorted_sessions[session.user.id] = user


sub: Subscriptor = Subscriptor()
