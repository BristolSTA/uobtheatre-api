"""
Utils
"""

import shortuuid


def create_short_uuid():
    return shortuuid.ShortUUID().random(length=12)
