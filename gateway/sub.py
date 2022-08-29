# The Derailed Gateway
#
# Copyright 2022 Derailed Inc. All rights reserved.
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
from gateway.models import Guild, Member, User

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
        self.consumer.subscribe(
            ['user', 'security', 'guild', 'track', 'relationships', 'presences']
        )
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
            elif message.name == 'GUILD_JOIN':
                user_sessions = self.user_id_sorted_sessions.get(message.user_id)

                if user_sessions is None:
                    continue

                FOUND_GUILD: bool = False

                for guild_id, sessions in self.guilds.items():
                    if guild_id != message.guild_id:
                        continue

                    new_sessions = sessions.add(self)
                    self.guilds[guild_id] = new_sessions
                    FOUND_GUILD = True
                    break

                if not FOUND_GUILD:
                    self.guilds[message.guild_id] = user_sessions

            elif message.name == 'GUILD_LEAVE':
                user_sessions = self.user_id_sorted_sessions.get(message.user_id)

                if user_sessions is None:
                    continue

                for guild_id, sessions in self.guilds.items():
                    if guild_id != message.guild_id:
                        continue

                    for user_session in user_sessions:
                        if user_session in sessions:
                            sessions.remove(user_session)

                    self.guilds[guild_id] = sessions
                    break

            if (
                message.user_id
                and message.name != 'GUILD_JOIN'
                and message.name != 'GUILD_LEAVE'
            ):
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

            elif message.guild_id:
                sessions = self.guilds.get(message.guild_id)

                if sessions is None:
                    continue

                websockets = []

                for session_id in sessions:
                    session = self.sessions.get(session_id)
                    websockets.append(session.ws)

                data = {
                    'op': 0,
                    't': message.name,
                    'd': message.data,
                }

                broadcast(websockets=websockets, message=data)

    async def subscribe(self, session: Session) -> None:
        self.sessions[session.session_id] = session
        if self.user_id_sorted_sessions.get(session.user.id) is None:
            self.user_id_sorted_sessions[session.user.id] = {session.session_id}
        else:
            self.user_id_sorted_sessions[session.user.id].add(session.session_id)

        joined_guild_members = Member.find(Member.user_id == session.user.id)

        async for member in joined_guild_members:
            if self.guilds.get(member.guild_id) is not None:
                self.guilds[member.guild_id].add(session.session_id)
            else:
                self.guilds[member.guild_id] = {session.session_id}

            guild = await Guild.find_one(Guild.id == member.guild_id)

            await session.send_event(0, guild.dict(), 'GUILD_CACHE')

    async def get_guild_members(
        self, session: Session, guild_id: str, limit: int | None
    ) -> None:
        members = Member.find(Member.guild_id == guild_id, limit=limit)

        async for member in members:
            dictified = member.dict(exclude={'user_id'})

            user = await User.find_one(User.id == member.user_id)
            dictified['user'] = user.dict(exclude={'password', 'email', 'verification'})

            await session.send_event(0, dictified, 'GUILD_MEMBER')

    def unsubscribe(self, session: Session) -> None:
        self.sessions.pop(session.session_id)
        user = self.user_id_sorted_sessions[session.user.id]
        user.remove(session.session_id)
        if len(user) == 0:
            self.user_id_sorted_sessions.pop(session.user.id)
        else:
            self.user_id_sorted_sessions[session.user.id] = user

        for guild_id, sessions in self.guilds.items():
            if session.session_id in sessions:
                sessions.remove(session.session_id)
                if sessions == {}:
                    self.guilds.pop(guild_id)
                else:
                    self.guilds[guild_id] = sessions


sub: Subscriptor = Subscriptor()
