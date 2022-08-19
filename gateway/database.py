# The Derailed Gateway
#
# Copyright 2022 Derailed. All rights reserved.
#
# Sharing of any piece of code to any unauthorized third-party is not allowed.
import os
from typing import Any

from beanie import init_beanie
from motor.motor_asyncio import AsyncIOMotorClient
from msgspec import Struct

from .models import Settings, User

DOCUMENT_MODELS = [
    User,
    Settings,
]


class Message(Struct):
    name: str
    data: dict[str, Any]
    user_id: str | None = None


async def connect() -> None:
    motor = AsyncIOMotorClient(os.getenv('MONGO_URI'))
    await init_beanie(
        database=motor.db_name,
        document_models=DOCUMENT_MODELS,
        allow_index_dropping=True,
    )
