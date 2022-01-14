from copy import deepcopy
from unittest.mock import PropertyMock, patch

import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.square_webhooks import SquareWebhooks
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.payments.transaction_providers import SquarePOS, SquareRefund

TEST_TERMINAL_CHECKOUT_PAYLOAD = {
    "merchant_id": "ML8M1AQ1GQG2K",
    "type": "terminal.checkout.updated",
    "event_id": "d395e3d0-1c5c-4372-bdf2-6955b8f44166",
    "created_at": "2021-08-13T13:45:52.789468835Z",
    "data": {
        "type": "checkout.event",
        "id": "dhgENdnFOPXqO",
        "object": {
            "checkout": {
                "amount_money": {"amount": 111, "currency": "USD"},
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
            }
        },
    },
}

TEST_PAYMENT_UPDATE_PAYLOAD = {
    "merchant_id": "ML8M1AQ1GQG2K",
    "type": "payment.updated",
    "event_id": "8abbbe96-02c3-4818-910f-43d4b83baef8",
    "created_at": "2021-10-03T11:18:16.523273578Z",
    "data": {
        "type": "payment",
        "id": "KkAkhdMsgzn59SM8A89WgKwekxLZY",
        "object": {
            "payment": {
                "amount_money": {"amount": 100, "currency": "USD"},
                "approved_money": {"amount": 100, "currency": "USD"},
                "card_details": {
                    "avs_status": "AVS_ACCEPTED",
                    "card": {
                        "bin": "540988",
                        "card_brand": "MASTERCARD",
                        "card_type": "CREDIT",
                        "exp_month": 11,
                        "exp_year": 2022,
                        "fingerprint": "sq-1-Tvruf3vPQxlvI6n0IcKYfBukrcv6IqWr8UyBdViWXU2yzGn5VMJvrsHMKpINMhPmVg",
                        "last_4": "9029",
                        "prepaid_type": "NOT_PREPAID",
                    },
                    "card_payment_timeline": {
                        "authorized_at": "2020-11-22T21:16:51.198Z",
                        "captured_at": "2020-11-22T21:19:00.832Z",
                    },
                    "cvv_status": "CVV_ACCEPTED",
                    "entry_method": "KEYED",
                    "statement_description": "SQ *DEFAULT TEST ACCOUNT",
                    "status": "CAPTURED",
                },
                "created_at": "2020-11-22T21:16:51.086Z",
                "delay_action": "CANCEL",
                "delay_duration": "PT168H",
                "delayed_until": "2020-11-29T21:16:51.086Z",
                "id": "hYy9pRFVxpDsO1FB05SunFWUe9JZY",
                "location_id": "S8GWD5R9QB376",
                "order_id": "03O3USaPaAaFnI6kkwB1JxGgBsUZY",
                "receipt_number": "hYy9",
                "receipt_url": "https://squareup.com/receipt/preview/hYy9pRFVxpDsO1FB05SunFWU11111",
                "risk_evaluation": {
                    "created_at": "2020-11-22T21:16:51.198Z",
                    "risk_level": "NORMAL",
                },
                "source_type": "CARD",
                "status": "COMPLETED",
                "total_money": {"amount": 100, "currency": "USD"},
                "updated_at": "2020-11-22T21:19:00.831Z",
                "version_token": "bhC3b8qKJvNDdxqKzXaeDsAjS1oMFuAKxGgT32HbE6S6o",
            }
        },
    },
}

TEST_UPDATE_REFUND_PAYLOAD = {
    "merchant_id": "ML8M1AQ1GQG2K",
    "type": "refund.updated",
    "event_id": "e4f5bcd7-6c4d-4c29-8637-115738d759e1",
    "created_at": "2021-12-13T21:01:40.805Z",
    "data": {
        "type": "refund",
        "id": "xwo62Kt4WIOAh9LrczZxzbQbIZCZY_RVpsRbbUP3LmklUotq0kfiJnn1jDOqhNHymoqa6iDpd",
        "object": {
            "refund": {
                "amount_money": {"amount": 100, "currency": "GBP"},
                "created_at": "2021-12-13T21:01:32.340Z",
                "id": "xwo62Kt4WIOAh9LrczZxzbQbIZCZY_RVpsRbbUP3LmklUotq0kfiJnn1jDOqhNHymoqa6iDpd",
                "location_id": "LN9PN3P67S0QV",
                "order_id": "tsjSHOoLci0yftfu8Z5BYFO2Me4F",
                "payment_id": "xwo62Kt4WIOAh9LrczZxzbQbIZCZY",
                "processing_fee": [
                    {
                        "amount_money": {"amount": -2, "currency": "GBP"},
                        "effective_at": "2021-04-15T13:27:08.000Z",
                        "type": "INITIAL",
                    },
                    {
                        "amount_money": {"amount": -5, "currency": "GBP"},
                        "effective_at": "2021-04-15T13:27:08.000Z",
                        "type": "INITIAL",
                    },
                ],
                "status": "COMPLETED",
                "updated_at": "2021-12-13T21:01:35.266Z",
                "version": 19,
            }
        },
    },
}


@pytest.mark.django_db
def test_handle_checkout_webhook(rest_client, monkeypatch):
    transaction = TransactionFactory(
        provider_transaction_id="dhgENdnFOPXqO", provider_name=SquarePOS.name
    )
    monkeypatch.setenv("SQUARE_WEBHOOK_SIGNATURE_KEY", "Hd_mmQkhER3EPkpRpNQh9Q")
    BookingFactory(reference="id72709", status=Payable.Status.IN_PROGRESS)

    with patch.object(
        SquareWebhooks, "webhook_url", new_callable=PropertyMock
    ) as url_mock, patch.object(
        SquareWebhooks, "webhook_signature_key", new_callable=PropertyMock
    ) as key_mock, patch.object(
        SquarePOS, "sync_transaction", autospec=True
    ) as sync_mock:
        url_mock.return_value = (
            "https://webhook.site/5bca8c49-e6f0-40ed-9415-4035bc05b48d"
        )
        key_mock.return_value = "Hd_mmQkhER3EPkpRpNQh9Q"

        response = rest_client.post(
            "/square",
            TEST_TERMINAL_CHECKOUT_PAYLOAD,
            HTTP_X_SQUARE_SIGNATURE="xoa9/2fAXamuULrlhV1HP7C4ai4=",
            format="json",
        )

    assert response.status_code == 200
    sync_mock.assert_called_once_with(transaction, None)


@pytest.mark.django_db
def test_handle_webhooks_invalid_signature(rest_client):
    booking = BookingFactory(reference="id72709", status=Payable.Status.IN_PROGRESS)
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
        provider_transaction_id="hYy9pRFVxpDsO1FB05SunFWUe9JZY", provider_fee=None
    )

    with patch.object(
        SquareWebhooks, "webhook_url", new_callable=PropertyMock
    ) as url_mock, patch.object(
        SquareWebhooks, "webhook_signature_key", new_callable=PropertyMock
    ) as key_mock:
        url_mock.return_value = (
            "https://webhook.site/b683d582-b125-401d-ae08-4453030fd84f"
        )
        key_mock.return_value = "1JKsHXm1f5TCz7PQGJDzSw"

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
    payment = TransactionFactory(
        provider_transaction_id="xwo62Kt4WIOAh9LrczZxzbQbIZCZY_RVpsRbbUP3LmklUotq0kfiJnn1jDOqhNHymoqa6iDpd",
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
