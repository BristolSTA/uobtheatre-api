from uobtheatre.utils.utils import create_short_uuid


def test_create_short_uuid_len():
    shortuuid = create_short_uuid()
    assert len(str(shortuuid)) == 12
