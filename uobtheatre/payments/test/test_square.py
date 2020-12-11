from uobtheatre.payments.square import square_init


def test_square_empty():
    result = square_init()
    assert result.status_code == 200
    assert True
