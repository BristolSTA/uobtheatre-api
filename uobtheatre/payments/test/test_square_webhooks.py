from unittest.mock import PropertyMock, patch

import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.payment_methods import SquarePOS

TEST_PAYLOAD = {
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


@pytest.mark.django_db
def test_handle_webhooks(rest_client, monkeypatch):
    monkeypatch.setenv("SQUARE_WEBHOOK_SIGNATURE_KEY", "Hd_mmQkhER3EPkpRpNQh9Q")
    booking = BookingFactory(
        reference="id72709", status=Booking.BookingStatus.IN_PROGRESS
    )

    with patch.object(
        SquarePOS, "webhook_url", new_callable=PropertyMock
    ) as url_mock, patch.object(
        SquarePOS, "webhook_signature_key", new_callable=PropertyMock
    ) as key_mock:
        url_mock.return_value = (
            "https://webhook.site/5bca8c49-e6f0-40ed-9415-4035bc05b48d"
        )
        key_mock.return_value = "Hd_mmQkhER3EPkpRpNQh9Q"

        response = rest_client.post(
            "/square",
            TEST_PAYLOAD,
            HTTP_X_SQUARE_SIGNATURE="xoa9/2fAXamuULrlhV1HP7C4ai4=",
            format="json",
        )

    assert response.status_code == 200
    booking.refresh_from_db()
    assert booking.status == Booking.BookingStatus.PAID


@pytest.mark.django_db
def test_handle_webhooks_invalid_signature(rest_client):
    booking = BookingFactory(
        reference="id72709", status=Booking.BookingStatus.IN_PROGRESS
    )
    response = rest_client.post(
        "/square",
        TEST_PAYLOAD,
        HTTP_X_SQUARE_SIGNATURE="xoa9/2fAXamuULrlhV1HP7C4ai4a",
        format="json",
    )
    assert response.status_code == 400
    assert response.data == "Invalid signature"

    booking.refresh_from_db()
    assert booking.status == Booking.BookingStatus.IN_PROGRESS
