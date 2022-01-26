from typing import Sized, Union


def pluralize(word, items: Union[Sized, int], plural_word=None, suffix="s"):
    count = items if isinstance(items, int) else abs(len(items))
    if count != 1:
        return word + suffix if not plural_word else plural_word
    return word
