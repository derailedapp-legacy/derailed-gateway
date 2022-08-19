# The Derailed Gateway
#
# Copyright 2022 Derailed. All rights reserved.
#
# Sharing of any piece of code to any unauthorized third-party is not allowed.
import asyncio
import os

import sentry_sdk
from dotenv import load_dotenv
from websockets.server import serve

from gateway import database
from gateway.session_maker import create_session


async def main():
    load_dotenv()
    sentry_dsn = os.getenv('SENTRY_DSN')
    if sentry_dsn is not None:
        sentry_sdk.init(dsn=sentry_dsn, traces_sample_rate=1.0)
        os.environ['SENTRY_ENABLED'] = 'true'
    else:
        os.environ['SENTRY_ENABLED'] = 'false'

    await database.connect()

    async with serve(
        create_session,
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000)),
        max_queue=None,
        ping_interval=45,
        ping_timeout=4,
    ):
        await asyncio.Future()


if __name__ == '__main__':
    asyncio.run(main())
