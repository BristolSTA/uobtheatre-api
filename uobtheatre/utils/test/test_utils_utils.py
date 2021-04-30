from uobtheatre.utils.utils import create_short_uuid


def test_create_short_uuid_len():
    shortuuid = create_short_uuid()
    assert len(str(shortuuid)) == 12


def test_create_short_uuid_uniqueness():
    shortuuid_one = create_short_uuid()
    shortuuid_two = create_short_uuid()

    assert shortuuid_one != shortuuid_two
