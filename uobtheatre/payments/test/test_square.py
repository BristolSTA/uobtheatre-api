from uobtheatre.payments.square import PaymentProvider


def test_square_list_payments():
    pp = PaymentProvider()
    result = pp.list_payments()
    assert result.status_code == 200
    assert result.body == {}


def test_square_create_payment():
    pp = PaymentProvider()
    result = pp.create_payment()
    assert result.status_code == 200
