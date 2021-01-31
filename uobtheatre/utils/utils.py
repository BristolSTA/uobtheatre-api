import shortuuid


def create_short_uuid():
    return shortuuid.ShortUUID().random(length=12)


def price_to_price_pounds(price_pennies):
    return "%.2f" % (price_pennies / 100)
