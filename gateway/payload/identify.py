# The Derailed Gateway
#
# Copyright 2022 Derailed Inc. All rights reserved.
#
# Sharing of any piece of code to any unauthorized third-party is not allowed.
from pydantic import BaseModel, Field


class Properties(BaseModel):
    os: str
    browser: str
    device: str
    library_github_repository: str | None = Field(max_length=100)
    client_version: str | None = Field(max_length=(6))


class Identify(BaseModel):
    token: str
    properties: Properties
