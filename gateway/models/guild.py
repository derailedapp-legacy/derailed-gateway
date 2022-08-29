# The Derailed API
#
# Copyright 2022 Derailed Inc. All rights reserved.
#
# Sharing of any piece of code to any unauthorized third-party is not allowed.
from datetime import datetime

from beanie import Document
from pydantic import Field


class Guild(Document):
    id: str
    name: str = Field(max_length=100)
    owner_id: str
    icon: str | None = None
    features: list[str] = []
    flags: int = 0
    description: str | None = Field(None, max_length=1300)
    nsfw: bool


class Member(Document):
    user_id: str
    guild_id: str
    nick: str | None
    joined_at: datetime
    role_ids: list[str]
