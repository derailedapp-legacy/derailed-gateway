# The Recorder Gateway
#
# Copyright 2022 Recorder, Inc. All rights reserved.
#
# Sharing of any piece of code to any unauthorized third-party is not allowed.
import os

from limits import parse
from limits.aio.strategies import FixedWindowRateLimiter
from limits.storage import storage_from_string

redis_uri = os.getenv('RATE_LIMIT_URI', 'memory://')
redis = storage_from_string(f'async+{redis_uri}')

window = FixedWindowRateLimiter(redis)
identify_concurrency = parse('1/5seconds')
identify_daily = parse('1000/day')
message_receive = parse('60/60seconds')
