from typing import Sized


def pluralize(word, items: Sized, plural_word=None, suffix="s"):
    count = abs(len(items))
    if count != 1:
        return word + suffix if not plural_word else plural_word
    return word
