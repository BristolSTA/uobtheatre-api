import random
import string


def create_random_ref(length=12):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=N))
