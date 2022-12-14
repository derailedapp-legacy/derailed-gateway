# The Derailed Gateway
#
# Copyright 2022 Derailed Inc. All rights reserved.
#
# Sharing of any piece of code to any unauthorized third-party is not allowed.
from typing import Any, Literal

from pydantic import BaseModel


class Receive(BaseModel):
    op: Literal[1, 4]
    d: dict[str, Any]
