from copy import deepcopy
from unittest.mock import patch

import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.square_webhooks import SquareWebhooks
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.payments.transaction_providers import SquarePOS, SquareRefund

TEST_TERMINAL_CHECKOUT_PAYLOAD = {
    "merchant_id": "7NZR58EPNGNPC",
    "type": "terminal.checkout.updated",
    "event_id": "1c3ef831-670d-4f4c-b59c-f0bb2d2fc872",
    "created_at": "2020-04-10T14:44:06.039Z",
    "data": {
        "type": "checkout",
        "id": "dhgENdnFOPXqO",
        "object": {
            "checkout": {
                "amount_money": {"amount": 111, "currency": "GBP"},
                "app_id": "sq0idp-734Md5EcFjFmwpaR0Snm6g",
                "created_at": "2020-04-10T14:43:55.262Z",
                "deadline_duration": "PT5M",
                "device_options": {
                    "device_id": "907CS13101300122",
                    "skip_receipt_screen": False,
                    "tip_settings": {"allow_tipping": False},
                },
                "id": "dhgENdnFOPXqO",
                "note": "A simple note",
                "payment_ids": ["dgzrZTeIeVuOGwYgekoTHsPouaB"],
                "reference_id": "id72709",
                "status": "COMPLETED",
                "updated_at": "2020-04-10T14:44:06.039Z",
                "location_id": "LMHPTEST",
            }
        },
    },
}

TEST_PAYMENT_UPDATE_PAYLOAD = {
    "merchant_id": "6SSW7HV8K2ST5",
    "type": "payment.updated",
    "event_id": "6a8f5f28-54a1-4eb0-a98a-3111513fd4fc",
    "created_at": "2020-02-06T21:27:34.308Z",
    "data": {
        "type": "payment",
        "id": "hYy9pRFVxpDsO1FB05SunFWUe9JZY",
        "object": {
            "payment": {
                "id": "hYy9pRFVxpDsO1FB05SunFWUe9JZY",
                "created_at": "2020-11-22T21:16:51.086Z",
                "updated_at": "2020-11-22T21:19:00.831Z",
                "amount_money": {"amount": 100, "currency": "GBP"},
                "status": "COMPLETED",
                "delay_duration": "PT168H",
                "source_type": "CARD",
                "card_details": {
                    "status": "CAPTURED",
                    "card": {
                        "card_brand": "MASTERCARD",
                        "last_4": "9029",
                        "exp_month": 11,
                        "exp_year": 2022,
                        "fingerprint": "sq-1-Tvruf3vPQxlvI6n0IcKYfBukrcv6IqWr8UyBdViWXU2yzGn5VMJvrsHMKpINMhPmVg",
                        "card_type": "CREDIT",
                        "prepaid_type": "NOT_PREPAID",
                        "bin": "540988",
                    },
                    "entry_method": "KEYED",
                    "cvv_status": "CVV_ACCEPTED",
                    "avs_status": "AVS_ACCEPTED",
                    "statement_description": "SQ *DEFAULT TEST ACCOUNT",
                    "card_payment_timeline": {
                        "authorized_at": "2020-11-22T21:16:51.198Z",
                        "captured_at": "2020-11-22T21:19:00.832Z",
                    },
                },
                "location_id": "LMHPTEST",
                "order_id": "03O3USaPaAaFnI6kkwB1JxGgBsUZY",
                "risk_evaluation": {
                    "created_at": "2020-11-22T21:16:51.198Z",
                    "risk_level": "NORMAL",
                },
                "total_money": {"amount": 100, "currency": "GBP"},
                "approved_money": {"amount": 100, "currency": "GBP"},
                "receipt_number": "hYy9",
                "receipt_url": "https://squareup.com/receipt/preview/hYy9pRFVxpDsO1FB05SunFWUe9JZY",
                "delay_action": "CANCEL",
                "delayed_until": "2020-11-29T21:16:51.086Z",
                "version_token": "bhC3b8qKJvNDdxqKzXaeDsAjS1oMFuAKxGgT32HbE6S6o",
            }
        },
    },
}

TEST_UPDATE_REFUND_PAYLOAD = {
    "merchant_id": "6SSW7HV8K2ST5",
    "type": "refund.updated",
    "event_id": "bc316346-6691-4243-88ed-6d651a0d0c47",
    "created_at": "2020-02-06T22:14:16.421Z",
    "data": {
        "type": "refund",
        "id": "KkAkhdMsgzn59SM8A89WgKwekxLZY_ptNBVqHYxt5gAdfcobBe4u1AZsXhoz06KTtuq9Ls24P",
        "object": {
            "refund": {
                "id": "KkAkhdMsgzn59SM8A89WgKwekxLZY_ptNBVqHYxt5gAdfcobBe4u1AZsXhoz06KTtuq9Ls24P",
                "created_at": "2020-02-06T21:27:41.836Z",
                "updated_at": "2020-02-06T22:14:16.381Z",
                "amount_money": {"amount": 100, "currency": "GBP"},
                "status": "COMPLETED",
                "processing_fee": [
                    {
                        "effective_at": "2020-02-06T23:27:31.000Z",
                        "type": "INITIAL",
                        "amount_money": {"amount": -5, "currency": "GBP"},
                    },
                    {
                        "effective_at": "2020-02-06T23:28:31.000Z",
                        "type": "INITIAL",
                        "amount_money": {"amount": -2, "currency": "GBP"},
                    },
                ],
                "location_id": "LMHPTEST",
                "order_id": "haOyDuHiqtAXMk0d8pDKXpL7Jg4F",
                "payment_id": "KkAkhdMsgzn59SM8A89WgKwekxLZY",
                "version": 10,
            }
        },
    },
}


@pytest.mark.parametrize(
    "object_data,expected_location",
    [
        (
            {"payment": {"location_id": "LOCATION123"}},
            "LOCATION123",
        ),
        (
            {"checkout": {"location_id": "LOCATION123"}},
            "LOCATION123",
        ),
        (
            {"refund": {"location_id": "LOCATION123"}},
            "LOCATION123",
        ),
        ({"invalid": {"location_id": "LOCATION123"}}, None),
    ],
)
def test_get_object_location_id(object_data, expected_location):
    assert (
        SquareWebhooks.get_object_location_id(object_data) == expected_location
    )


@pytest.mark.django_db
def test_handle_checkout_webhook(rest_client):
    transaction = TransactionFactory(
        provider_transaction_id="dhgENdnFOPXqO", provider_name=SquarePOS.name
    )

    BookingFactory(reference="id72709", status=Payable.Status.IN_PROGRESS)

    with patch.object(
        SquareWebhooks, "is_valid_callback", return_value=True
    ), patch.object(SquarePOS, "sync_transaction", autospec=True) as sync_mock:
        response = rest_client.post(
            "/square",
            TEST_TERMINAL_CHECKOUT_PAYLOAD,
            HTTP_X_SQUARE_SIGNATURE="xoa9/2fAXamuULrlhV1HP7C4ai4=",
            format="json",
        )

    assert response.status_code == 200
    sync_mock.assert_called_once_with(transaction, None)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,expected_code", [("COMPLETED", 404), ("CANCELED", 201)]
)
def test_handle_checkout_webhook_with_unknown_transaction(
    status, expected_code, rest_client
):
    payload = deepcopy(TEST_TERMINAL_CHECKOUT_PAYLOAD)
    payload["data"]["object"]["checkout"]["status"] = status

    with patch.object(SquareWebhooks, "is_valid_callback", return_value=True):
        response = rest_client.post(
            "/square",
            payload,
            HTTP_X_SQUARE_SIGNATURE="signature",
            format="json",
        )
    assert response.status_code == expected_code


@pytest.mark.django_db
def test_handle_webhooks_invalid_signature(rest_client):
    booking = BookingFactory(
        reference="id72709", status=Payable.Status.IN_PROGRESS
    )
    response = rest_client.post(
        "/square",
        TEST_TERMINAL_CHECKOUT_PAYLOAD,
        HTTP_X_SQUARE_SIGNATURE="xoa9/2fAXamuULrlhV1HP7C4ai4a",
        format="json",
    )
    assert response.status_code == 400
    assert response.data == "Invalid signature"

    booking.refresh_from_db()
    assert booking.status == Payable.Status.IN_PROGRESS


@pytest.mark.django_db
def test_handle_payment_update_webhook_no_processing_fee(rest_client):
    payment = TransactionFactory(
        provider_transaction_id="hYy9pRFVxpDsO1FB05SunFWUe9JZY",
        provider_fee=None,
    )

    with patch.object(SquareWebhooks, "is_valid_callback", return_value=True):
        response = rest_client.post(
            "/square",
            TEST_PAYMENT_UPDATE_PAYLOAD,
            HTTP_X_SQUARE_SIGNATURE="IoIb9bsLtyTbTcr+l2Ic039gOuo=",
            format="json",
        )

    assert response.status_code == 200
    assert payment.provider_fee is None


@pytest.mark.django_db
def test_handle_payment_update_webhook(rest_client):
    payment = TransactionFactory(
        provider_transaction_id="hYy9pRFVxpDsO1FB05SunFWUe9JZY", provider_fee=0
    )

    payload = deepcopy(TEST_PAYMENT_UPDATE_PAYLOAD)
    payload["data"]["object"]["payment"]["processing_fee"] = [
        {
            "effective_at": "2021-10-03T09:46:42.000Z",
            "type": "INITIAL",
            "amount_money": {"amount": 58, "currency": "GBP"},
        },
        {
            "effective_at": "2021-10-03T09:46:42.000Z",
            "type": "INITIAL",
            "amount_money": {"amount": 12, "currency": "GBP"},
        },
    ]

    with patch.object(SquareWebhooks, "is_valid_callback", return_value=True):
        response = rest_client.post(
            "/square",
            payload,
            HTTP_X_SQUARE_SIGNATURE="signature",
            format="json",
        )

    payment.refresh_from_db()
    assert response.status_code == 200
    assert payment.provider_fee == 70


@pytest.mark.django_db
def test_handle_payment_update_checkout_webhook(rest_client):
    payment = TransactionFactory(
        provider_transaction_id="dhgENdnFOPXqO",
        provider_fee=0,
        provider_name=SquarePOS.name,
    )

    payload = deepcopy(TEST_PAYMENT_UPDATE_PAYLOAD)
    payload["data"]["object"]["payment"][
        "terminal_checkout_id"
    ] = "dhgENdnFOPXqO"

    with patch.object(
        SquareWebhooks, "is_valid_callback", return_value=True
    ), patch.object(SquarePOS, "sync_transaction", autospec=True) as sync_mock:
        rest_client.post(
            "/square",
            payload,
            HTTP_X_SQUARE_SIGNATURE="signature",
            format="json",
        )

    sync_mock.assert_called_once_with(payment, None)


@pytest.mark.django_db
def test_square_webhook_unknown_type(rest_client):
    with patch.object(SquareWebhooks, "is_valid_callback", return_value=True):
        response = rest_client.post(
            "/square",
            {
                "type": "unknown.type",
            },
            HTTP_X_SQUARE_SIGNATURE="signature",
            format="json",
        )

    assert response.status_code == 202


@pytest.mark.django_db
def test_handle_refund_update_webhook(rest_client):
    booking = BookingFactory()
    payment = TransactionFactory(
        pay_object=booking,
        provider_transaction_id="KkAkhdMsgzn59SM8A89WgKwekxLZY_ptNBVqHYxt5gAdfcobBe4u1AZsXhoz06KTtuq9Ls24P",
        provider_fee=0,
        type=Transaction.Type.REFUND,
        provider_name=SquareRefund.name,
    )

    with patch.object(SquareWebhooks, "is_valid_callback", return_value=True):
        response = rest_client.post(
            "/square",
            TEST_UPDATE_REFUND_PAYLOAD,
            HTTP_X_SQUARE_SIGNATURE="signature",
            format="json",
        )

    payment.refresh_from_db()
    assert response.status_code == 200
    assert payment.provider_fee == -7
    assert payment.status == Transaction.Status.COMPLETED
    booking.refresh_from_db()
    assert payment.pay_object.status == Payable.Status.REFUNDED


@pytest.mark.django_db
def test_handle_valid_but_unknown_transaction(rest_client):
    with patch.object(SquareWebhooks, "is_valid_callback", return_value=True):
        response = rest_client.post(
            "/square",
            TEST_PAYMENT_UPDATE_PAYLOAD,
            HTTP_X_SQUARE_SIGNATURE="signature",
            format="json",
        )
    assert response.status_code == 404


@pytest.mark.django_db
def test_handle_valid_but_unknown_transaction_other_location(rest_client):
    payload = deepcopy(TEST_PAYMENT_UPDATE_PAYLOAD)
    payload["data"]["object"]["payment"]["location_id"] = "LMHPTESTUNKNOWN"

    with patch.object(SquareWebhooks, "is_valid_callback", return_value=True):
        response = rest_client.post(
            "/square",
            payload,
            HTTP_X_SQUARE_SIGNATURE="signature",
            format="json",
        )
    assert response.status_code == 203
