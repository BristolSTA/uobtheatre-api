import pytest

from uobtheatre.utils.utils import create_short_uuid, deep_get


def test_create_short_uuid_len():
    shortuuid = create_short_uuid()
    assert len(str(shortuuid)) == 12


def test_create_short_uuid_uniqueness():
    shortuuid_one = create_short_uuid()
    shortuuid_two = create_short_uuid()

    assert shortuuid_one != shortuuid_two


@pytest.mark.parametrize(
    "keys,expected",
    [
        ("level2", None),
        ("level2.level3", None),
        (
            "level1",
            {
                "level12a": True,
                "level12b": "stringAtLevel12b",
                "level12c": {"level13a": 123},
            },
        ),
        ("level1.level12a", True),
        ("level1.level12d", None),
        ("level1.level12b", "stringAtLevel12b"),
        ("level1.level12c.level13a", 123),
    ],
)
def test_deep_get(keys, expected):
    data = {
        "level1": {
            "level12a": True,
            "level12b": "stringAtLevel12b",
            "level12c": {"level13a": 123},
        }
    }

    assert deep_get(data, keys) == expected
