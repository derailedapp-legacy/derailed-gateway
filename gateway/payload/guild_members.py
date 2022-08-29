# The Derailed Gateway
#
# Copyright 2022 Derailed Inc. All rights reserved.
#
# Sharing of any piece of code to any unauthorized third-party is not allowed.
from pydantic import BaseModel


class GetGuildMembers(BaseModel):
    guild_id: str
    limit: int | None = None
