import pytest

from uobtheatre.utils.lang import pluralize


@pytest.mark.parametrize(
    "word,num_items,suffix,plural_word,expected",
    [
        ("cat", -1, None, None, "cats"),
        ("cat", 0, None, None, "cats"),
        ("cat", 1, None, None, "cat"),
        ("cat", 2, None, None, "cats"),
        ("cat", 3, None, None, "cats"),
        ("dog", 1, "gys", None, "dog"),
        ("dog", 2, "gys", None, "doggys"),
        ("mouse", 1, None, "mice", "mouse"),
        ("mouse", 2, None, "mice", "mice"),
        ("mouse", 2, "es", "mice", "mice"),
    ],
)
def test_pluralize(word, num_items, suffix, plural_word, expected):
    args = {"word": word}
    if suffix:
        args["suffix"] = suffix
    if plural_word:
        args["plural_word"] = plural_word
    assert pluralize(items=range(num_items), **args) == expected
    assert pluralize(items=num_items, **args) == expected
