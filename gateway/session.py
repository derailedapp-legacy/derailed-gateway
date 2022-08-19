# The Derailed Gateway
#
# Copyright 2022 Derailed. All rights reserved.
#
# Sharing of any piece of code to any unauthorized third-party is not allowed.
import asyncio
import os
import traceback
from secrets import token_hex
from typing import Any

import sentry_sdk
from msgspec import DecodeError, json
from pydantic import ValidationError
from websockets.exceptions import ConnectionClosed, ConnectionClosedOK
from websockets.server import WebSocketServerProtocol

from gateway.payload import identify, receive
from gateway.rate_limit import (
    identify_concurrency,
    identify_daily,
    message_receive,
    window,
)

from .auth import verify_token
from .models.user import Settings, User
from .sub import sub


class DisconnectException(Exception):
    def __init__(self, code: int, reason: str) -> None:
        super().__init__(code, reason)
        self.code = code
        self.reason = reason


OPS = {0: 'dispatch', 1: 'identify', 2: 'exception', 3: 'hello'}


class Session:
    def __init__(self, ws: WebSocketServerProtocol) -> None:
        self.ws = ws
        self.user: User = None
        self.ready: bool = False
        self.session_id: str = token_hex(16)

    async def send_event(
        self, operation: int, data: dict[str, Any], type: str | None = None
    ) -> None:
        data_sent = {
            'op': operation,
            't': type,
            'd': data,
        }
        # TODO: Encryption with zlib
        await self.ws.send(json.encode(data_sent))

    async def send_exception(self, type: str, reason: str) -> None:
        await self.send_event(2, {'type': type, 'reason': reason})

    async def on_identify(self, data: dict[str, Any]) -> None:
        try:
            ident = identify.Identify.validate(data)
        except ValidationError:
            raise DisconnectException(4000, 'Invalid Identify data')

        user = await verify_token(token=ident.token)

        if user is None:
            raise DisconnectException(4001, 'Invalid Token')

        self.user = user

        concurrency_rate_limit = await window.hit(identify_concurrency, user.id)

        if concurrency_rate_limit is False:
            raise DisconnectException(
                4002, 'Maximum concurrent connections every 5 seconds reached.'
            )

        daily_rate_limit = await window.hit(identify_daily, user.id)

        if daily_rate_limit is False:
            raise DisconnectException(4003, 'Maximum daily connections (1000) reached.')

        await self.get_ready()
        self.ready = True
        sub.subscribe(session=self)

    async def get_ready(self) -> None:
        settings = await Settings.find_one(Settings.id == self.user.id)

        ready_data = {
            'user': self.user.dict(exclude={'password'}),
            'settings': settings.dict(exclude={'id'}),
        }
        await self.send_event(operation=0, data=ready_data, type='READY')

    async def on_event(self, data: str) -> None:
        if self.ready:
            rate_limit = await window.hit(
                message_receive, self.user.id, self.session_id
            )

            if rate_limit is False:
                raise DisconnectException(
                    4004, 'Message Receive Rate Limit (60/60) passed.'
                )

        try:
            j = json.decode(data.encode(), type=dict)
            d = receive.Receive.validate(j)
        except DecodeError:
            await self.send_exception('INVALID_JSON', 'json sent was invalid')
        except ValidationError as exc:
            await self.send_exception('INVALID_DATA', exc.json(None))

        if d.op != 1 and not self.ready:
            raise DisconnectException(4007, 'Unauthorized Rate Limit (1) passed.')

        if d.op == 1:
            await self.on_identify(d.d)

    async def loop_receive(self) -> None:
        async for msg in self.ws:
            if isinstance(msg, bytes):
                try:
                    data = msg.decode('utf-8')
                except UnicodeDecodeError:
                    continue
            elif isinstance(msg, str):
                data = msg
            else:
                raise DisconnectException(4005, 'Unsupported data type given')

            asyncio.create_task(self.on_event(data=data))

    async def _disconnect(self, reason: str) -> None:
        await self.ws.close(4008, reason=reason)
        self._recv_task.cancel()

    async def run(self) -> None:
        try:
            await sub.make_ready()
            await self.send_event(3, {'session_id': self.session_id})
            self._recv_task = asyncio.create_task(self.loop_receive())
            await self._recv_task
        except (ConnectionClosed, ConnectionClosedOK, asyncio.CancelledError):
            pass
        except DisconnectException as exc:
            await self.ws.close(exc.code, exc.reason)
        except Exception as exc:
            await self.ws.close(4006, 'Unknown exception occured')
            if os.environ['SENTRY_ENABLED'] == 'true':
                sentry_sdk.capture_exception(exc)
            else:
                traceback.print_exception(exc)
        finally:
            if self.ready:
                sub.unsubscribe(session=self)
