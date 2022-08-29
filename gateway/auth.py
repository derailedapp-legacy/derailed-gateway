# The Derailed Gateway
#
# Copyright 2022 Derailed Inc. All rights reserved.
#
# Sharing of any piece of code to any unauthorized third-party is not allowed.
import base64
import binascii

import itsdangerous

from .models.user import User


async def verify_token(token: str) -> User | None:
    fragmented = token.split('.')
    encoded_user_id = fragmented[0]

    try:
        user_id = base64.b64decode(encoded_user_id.encode()).decode()
    except (ValueError, binascii.Error):
        return None

    user = await User.find_one(User.id == user_id)

    if user is None:
        return None

    signer = itsdangerous.TimestampSigner(user.password)

    try:
        signer.unsign(token)

        return user
    except (itsdangerous.BadSignature):
        return None
