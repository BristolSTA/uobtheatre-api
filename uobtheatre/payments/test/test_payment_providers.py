# pylint: disable=too-many-lines
from unittest.mock import PropertyMock, patch

import pytest
from square.core.pagination import SyncPager
from square.types.card import Card as SquareCard
from square.types.card_payment_details import CardPaymentDetails
from square.types.create_payment_response import CreatePaymentResponse
from square.types.create_terminal_checkout_response import (
    CreateTerminalCheckoutResponse,
)
from square.types.device_checkout_options import DeviceCheckoutOptions
from square.types.device_code import DeviceCode
from square.types.error import Error
from square.types.get_payment_response import GetPaymentResponse
from square.types.money import Money
from square.types.payment import Payment
from square.types.terminal_checkout import TerminalCheckout

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.exceptions import (
    CantBeCanceledException,
    CantBeRefundedException,
)
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.square_webhooks import SquareWebhooks
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.payments.transaction_providers import (
    Card,
    Cash,
    ManualCardRefund,
    PaymentProvider,
    RefundProvider,
    SquareOnline,
    SquarePOS,
    SquareRefund,
    TransactionProvider,
)
from uobtheatre.utils.exceptions import PaymentException, SquareException


def test_payment_method_all():
    assert PaymentProvider.__all__ == [
        Cash,
        Card,
        SquarePOS,
        SquareOnline,
    ]


def test_transaction_method_all():
    assert TransactionProvider.__all__ == [  # pylint: disable=comparison-with-callable
        Cash,
        Card,
        SquarePOS,
        SquareOnline,
        ManualCardRefund,
        SquareRefund,
    ]


def test_payment_method_choice():
    assert PaymentProvider.choices == [  # pylint: disable=comparison-with-callable
        ("CASH", "CASH"),
        ("CARD", "CARD"),
        ("SQUARE_POS", "SQUARE_POS"),
        ("SQUARE_ONLINE", "SQUARE_ONLINE"),
    ]


@pytest.mark.parametrize(
    "payment_id, raises_exception",
    [
        (None, True),
        ("", True),
        ("123", False),
        ("abc", False),
    ],
)
def test_get_provider_transaction_id(payment_id, raises_exception):
    payment = Transaction()
    payment.provider_transaction_id = payment_id

    if raises_exception:
        with pytest.raises(PaymentException):
            TransactionProvider.get_payment_provider_id(payment)
    else:
        assert TransactionProvider.get_payment_provider_id(payment) == payment_id


@pytest.mark.parametrize(
    "payment_method, expected_name",
    [
        (SquareOnline, "SQUARE_ONLINE"),
        (SquarePOS, "SQUARE_POS"),
        (SquarePOS("123", "ikey"), "SQUARE_POS"),
    ],
)
def test_payment_method_name(payment_method, expected_name):
    assert payment_method.name == expected_name


@pytest.mark.parametrize(
    "input_name, expected_output_name",
    [
        ("SquareOnline", "SQUARE_ONLINE"),
        ("ABC", "ABC"),
        ("ABCOnline", "ABC_ONLINE"),
    ],
)
def test_generate_name(input_name, expected_output_name):
    assert PaymentProvider.generate_name(input_name) == expected_output_name


@pytest.mark.django_db
@pytest.mark.parametrize(
    "payment_method, expected_type",
    [
        (SquareOnline, Transaction.Type.PAYMENT),
        (SquareRefund, Transaction.Type.REFUND),
    ],
)
def test_create_payment_object(payment_method, expected_type):
    booking = BookingFactory()
    payment_method.create_payment_object(booking, 10, 5, currency="ABC")

    assert Transaction.objects.count() == 1
    payment = Transaction.objects.first()

    assert payment.provider_name == payment_method.name
    assert payment.type == expected_type
    assert payment.pay_object == booking
    assert payment.value == 10
    assert payment.currency == "ABC"
    assert payment.app_fee == 5


###
# Square Online PaymentMethod
###
@pytest.mark.django_db
@pytest.mark.parametrize("with_sca_token", [True, False])
def test_square_online_pay_success(mock_square, with_sca_token):
    """
    Test paying a booking with square
    """

    mock_response = CreatePaymentResponse(
        payment={
            "id": "abc",
            "card_details": {
                "card": {
                    "card_brand": "MASTERCARD",
                    "last4": "1234",
                }
            },
            "amount_money": {
                "currency": "GBP",
                "amount": 10,
            },
        }
    )

    with mock_square(SquareOnline.client.payments, "create", mock_response) as mock:
        booking = BookingFactory(reference="abcd")
        payment_method = SquareOnline(
            "nonce", "key", "verify_token" if with_sca_token else None
        )
        payment = payment_method.pay(20, 10, booking)

    # Assert the returned payment gets saved
    assert Transaction.objects.count() == 1
    assert Transaction.objects.first() == payment

    if with_sca_token:
        mock.assert_called_once_with(
            idempotency_key="key",
            source_id="nonce",
            amount_money={"amount": 20, "currency": "GBP"},
            reference_id="abcd",
            verification_token="verify_token",
        )
    else:
        mock.assert_called_once_with(
            idempotency_key="key",
            source_id="nonce",
            amount_money={"amount": 20, "currency": "GBP"},
            reference_id="abcd",
        )

    # Assert a payment of the correct type is created
    assert payment is not None
    assert payment.pay_object == booking
    assert payment.value == 10
    assert payment.currency == "GBP"
    assert payment.card_brand == "MASTERCARD"
    assert payment.last_4 == "1234"
    assert payment.provider_transaction_id == "abc"
    assert payment.provider_name == "SQUARE_ONLINE"
    assert payment.type == Transaction.Type.PAYMENT
    assert payment.status == Transaction.Status.COMPLETED
    assert payment.app_fee == 10

    assert payment.provider_fee is None


@pytest.mark.django_db
def test_square_online_pay_api_failure(mock_square):
    """
    Test paying a booking with square
    """
    with mock_square(
        SquareOnline.client.payments,
        "create",
        throw_default_exception=True,
    ):
        payment_method = SquareOnline("nonce", "abc")
        with pytest.raises(SquareException):
            payment_method.pay(100, 0, BookingFactory())

    # Assert no payments are created
    assert Transaction.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "response",
    [
        CreatePaymentResponse(),
        CreatePaymentResponse(
            errors=[
                Error(
                    category="API_ERROR",
                    code="INVALID_REQUEST_ERROR",
                    detail="Invalid request",
                )
            ]
        ),
        CreatePaymentResponse(
            payment=Payment(
                id="abc",
                amount_money=Money(
                    currency="GBP",
                    amount=10,
                ),
            )
        ),
        CreatePaymentResponse(
            payment=Payment(
                id="abc",
                amount_money=Money(
                    currency="GBP",
                    amount=10,
                ),
            ),
            errors=[
                Error(
                    category="API_ERROR",
                    code="INVALID_REQUEST_ERROR",
                    detail="Invalid request",
                )
            ],
        ),
        CreatePaymentResponse(
            payment=Payment(
                id="abc",
                card_details=CardPaymentDetails(),
                amount_money=Money(
                    currency="GBP",
                    amount=10,
                ),
            ),
        ),
        CreatePaymentResponse(
            payment=Payment(
                id="abc",
                card_details=CardPaymentDetails(),
                amount_money=Money(
                    currency="GBP",
                    amount=10,
                ),
            ),
            errors=[
                Error(
                    category="API_ERROR",
                    code="INVALID_REQUEST_ERROR",
                    detail="Invalid request",
                )
            ],
        ),
        CreatePaymentResponse(
            payment=Payment(
                id="abc",
                card_details=CardPaymentDetails(
                    card=SquareCard(
                        card_brand="MASTERCARD",
                        last4="1234",
                    ),
                ),
            ),
        ),
        CreatePaymentResponse(
            payment=Payment(
                id="abc",
                card_details=CardPaymentDetails(
                    card=SquareCard(
                        card_brand="MASTERCARD",
                        last4="1234",
                    ),
                ),
            ),
            errors=[
                Error(
                    category="API_ERROR",
                    code="INVALID_REQUEST_ERROR",
                    detail="Invalid request",
                )
            ],
        ),
        CreatePaymentResponse(
            payment=Payment(
                card_details=CardPaymentDetails(
                    card=SquareCard(
                        card_brand="MASTERCARD",
                        last4="1234",
                    ),
                ),
                amount_money=Money(
                    currency="GBP",
                    amount=10,
                ),
            ),
        ),
        CreatePaymentResponse(
            payment=Payment(
                card_details=CardPaymentDetails(
                    card=SquareCard(
                        card_brand="MASTERCARD",
                        last4="1234",
                    ),
                ),
                amount_money=Money(
                    currency="GBP",
                    amount=10,
                ),
            ),
            errors=[
                Error(
                    category="API_ERROR",
                    code="INVALID_REQUEST_ERROR",
                    detail="Invalid request",
                )
            ],
        ),
    ],
)
def test_square_online_pay_payment_failure(mock_square, response):
    with mock_square(
        SquareOnline.client.payments,
        "create",
        response,
    ):
        payment_method = SquareOnline("nonce", "abc")
        with pytest.raises(PaymentException):
            payment_method.pay(100, 0, BookingFactory())

    # Assert no payments are created
    assert Transaction.objects.count() == 0


@pytest.mark.django_db
def test_square_online_sync_payment(mock_square):
    payment = TransactionFactory(
        value=100, provider_fee=None, status=Transaction.Status.PENDING
    )

    mock_response = GetPaymentResponse(
        payment={
            "id": "abc",
            "status": "COMPLETED",
            "processing_fee": [{"amount_money": {"amount": -10, "currency": "GBP"}}],
        }
    )

    with mock_square(
        SquareOnline.client.payments,
        "get",
        mock_response,
    ):
        payment.sync_transaction_with_provider()
        payment.refresh_from_db()
    assert payment.provider_fee == -10
    assert payment.status == Transaction.Status.COMPLETED


@pytest.mark.django_db
def test_square_online_sync_payment_no_status(mock_square):
    payment = TransactionFactory(
        value=100, provider_fee=None, status=Transaction.Status.PENDING
    )

    mock_response = GetPaymentResponse(
        payment={
            "id": "abc",
            "processing_fee": [{"amount_money": {"amount": -10, "currency": "GBP"}}],
        }
    )

    with mock_square(
        SquareOnline.client.payments,
        "get",
        mock_response,
    ):
        with pytest.raises(PaymentException):
            payment.sync_transaction_with_provider()

    # Assert the payment is not updated
    payment.refresh_from_db()
    assert payment.status == Transaction.Status.PENDING


@pytest.mark.django_db
def test_square_online_sync_payment_no_payment(mock_square):
    payment = TransactionFactory(
        value=100, provider_fee=None, status=Transaction.Status.PENDING
    )

    mock_response = GetPaymentResponse()

    with mock_square(
        SquareOnline.client.payments,
        "get",
        mock_response,
    ):
        with pytest.raises(PaymentException):
            payment.sync_transaction_with_provider()

        payment.refresh_from_db()

    assert payment.provider_fee is None
    assert payment.status == Transaction.Status.PENDING


@pytest.mark.django_db
def test_square_online_cancel_payment():
    transaction = TransactionFactory(provider_name=SquareOnline.name)
    SquareOnline.cancel(transaction)
    assert Transaction.objects.filter(pk=transaction.pk).exists()


###
# Square POS PaymentMethod
###
@pytest.mark.django_db
def test_square_pos_pay_success(mock_square):

    mock_response = CreateTerminalCheckoutResponse(
        checkout={
            "id": "ScegTcoaJ0kqO",
            "amount_money": {"amount": 100, "currency": "GBP"},
            "device_options": {
                "device_id": "121CS145A5000029",
            },
            "status": "PENDING",
        }
    )

    with mock_square(
        SquarePOS.client.terminal.checkouts,
        "create",
        mock_response,
    ):
        payment_method = SquarePOS("device_id", "ikey")
        payment_method.pay(100, 14, BookingFactory())

    # Assert a payment is created that links to the checkout.
    assert Transaction.objects.count() == 1

    payment = Transaction.objects.first()
    assert payment.value == 100
    assert payment.status == Transaction.Status.PENDING
    assert payment.app_fee == 14
    assert payment.provider_fee is None
    assert payment.provider_transaction_id == "ScegTcoaJ0kqO"


@pytest.mark.django_db
def test_square_pos_pay_api_failure(mock_square):
    with mock_square(
        SquarePOS.client.terminal.checkouts,
        "create",
        throw_default_exception=True,
    ):
        with pytest.raises(SquareException):
            payment_method = SquarePOS("device_id", "ikey")
            payment_method.pay(100, 0, BookingFactory())

    # Assert no payments are created
    assert Transaction.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "response",
    [
        CreateTerminalCheckoutResponse(),
        CreateTerminalCheckoutResponse(
            errors=[
                Error(
                    category="API_ERROR",
                    code="INVALID_REQUEST_ERROR",
                    detail="Invalid request",
                )
            ]
        ),
        CreateTerminalCheckoutResponse(
            checkout=TerminalCheckout(
                amount_money=Money(
                    amount=100,
                    currency="GBP",
                ),
                device_options=DeviceCheckoutOptions(
                    device_id="abc",
                    skip_receipt_screen=False,
                ),
                status="PENDING",
            )
        ),
        CreateTerminalCheckoutResponse(
            checkout=TerminalCheckout(
                amount_money=Money(
                    amount=100,
                    currency="GBP",
                ),
                device_options=DeviceCheckoutOptions(
                    device_id="abc",
                    skip_receipt_screen=False,
                ),
                status="PENDING",
            ),
            errors=[
                Error(
                    category="API_ERROR",
                    code="INVALID_REQUEST_ERROR",
                    detail="Invalid request",
                )
            ],
        ),
    ],
)
def test_square_pos_pay_payment_failure(mock_square, response):
    with mock_square(SquarePOS.client.terminal.checkouts, "create", response):
        with pytest.raises(PaymentException):
            payment_method = SquarePOS("device_id", "ikey")
            payment_method.pay(100, 0, BookingFactory())

    # Assert no payments are created
    assert Transaction.objects.count() == 0


@pytest.mark.django_db
def test_square_pos_list_devices_success(mock_square):
    mock_response = SyncPager(
        has_next=False,
        items=[
            DeviceCode(
                device_id="a",
            ),
            DeviceCode(
                device_id="b",
            ),
            DeviceCode(
                device_id="c",
            ),
        ],
        get_next=None,
    )

    with mock_square(
        SquarePOS.client.devices.codes,
        "list",
        mock_response,
    ):
        assert SquarePOS.list_devices() == [
            DeviceCode(
                device_id="a",
            ),
            DeviceCode(
                device_id="b",
            ),
            DeviceCode(
                device_id="c",
            ),
        ]


@pytest.mark.django_db
def test_square_pos_list_devices_failure(mock_square):
    with mock_square(
        SquarePOS.client.devices.codes,
        "list",
        throw_default_exception=True,
    ):
        with pytest.raises(SquareException):
            SquarePOS.list_devices()


@pytest.mark.django_db
def test_square_get_checkout_error(mock_square):
    with mock_square(
        SquarePOS.client.terminal.checkouts,
        "get",
        throw_default_exception=True,
    ):
        with pytest.raises(SquareException):
            SquarePOS.get_checkout("abc")


@pytest.mark.django_db
def test_square_get_checkout(mock_square):
    mock_response = CreateTerminalCheckoutResponse(
        checkout={
            "id": "08YceKh7B3ZqO",
            "amount_money": {"amount": 2610, "currency": "GBP"},
            "reference_id": "id11572",
            "note": "A brief note",
            "device_options": {
                "device_id": "dbb5d83a-7838-11ea-bc55-0242ac130003",
                "tip_settings": {"allow_tipping": False},
                "skip_receipt_screen": False,
            },
            "status": "IN_PROGRESS",
            "location_id": "LOCATION_ID",
            "created_at": "2020-04-06T16:39:32.545Z",
            "updated_at": "2020-04-06T16:39:323.001Z",
            "app_id": "APP_ID",
            "deadline_duration": "PT5M",
        }
    )

    with mock_square(
        SquarePOS.client.terminal.checkouts,
        "get",
        mock_response,
    ):
        assert SquarePOS.get_checkout("08YceKh7B3ZqO") == TerminalCheckout(
            id="08YceKh7B3ZqO",
            amount_money={"amount": 2610, "currency": "GBP"},
            reference_id="id11572",
            note="A brief note",
            device_options={
                "device_id": "dbb5d83a-7838-11ea-bc55-0242ac130003",
                "tip_settings": {"allow_tipping": False},
                "skip_receipt_screen": False,
            },
            status="IN_PROGRESS",
            location_id="LOCATION_ID",
            created_at="2020-04-06T16:39:32.545Z",
            updated_at="2020-04-06T16:39:323.001Z",
            app_id="APP_ID",
            deadline_duration="PT5M",
        )


@pytest.mark.django_db
def test_square_pos_cancel_api_failure(mock_square):
    payment = TransactionFactory()

    with mock_square(
        SquarePOS.client.terminal.checkouts,
        "cancel",
        throw_default_exception=True,
    ):
        with pytest.raises(SquareException):
            payment_method = SquarePOS("device_id", "ikey")
            payment_method.cancel(payment)


@pytest.mark.django_db
def test_square_pos_cancel_payment_failure(mock_square):
    payment = TransactionFactory(provider_transaction_id=None)

    with mock_square(
        SquarePOS.client.terminal.checkouts,
        "cancel",
    ):
        with pytest.raises(PaymentException):
            payment_method = SquarePOS("device_id", "ikey")
            payment_method.cancel(payment)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "checkout_return,expected_transaction_status,expected_booking_status",
    [
        (
            TerminalCheckout(
                id="abc",
                status="COMPLETED",
                payment_ids=["abc123"],
                amount_money=Money(
                    amount=100,
                    currency="GBP",
                ),
                device_options=DeviceCheckoutOptions(
                    device_id="abc",
                    skip_receipt_screen=False,
                ),
            ),
            Transaction.Status.COMPLETED,
            Payable.Status.PAID,
        ),
        (
            TerminalCheckout(
                id="abc",
                status="CANCELED",
                payment_ids=["abc123"],
                amount_money=Money(
                    amount=100,
                    currency="GBP",
                ),
                device_options=DeviceCheckoutOptions(
                    device_id="abc",
                    skip_receipt_screen=False,
                ),
            ),
            Transaction.Status.FAILED,
            Payable.Status.IN_PROGRESS,
        ),
        (
            TerminalCheckout(
                id="abc",
                status="PENDING",
                payment_ids=["abc123"],
                amount_money=Money(
                    amount=100,
                    currency="GBP",
                ),
                device_options=DeviceCheckoutOptions(
                    device_id="abc",
                    skip_receipt_screen=False,
                ),
            ),
            Transaction.Status.PENDING,
            Payable.Status.IN_PROGRESS,
        ),
    ],
)
def test_square_pos_sync_payment(
    checkout_return, expected_transaction_status, expected_booking_status
):
    payment = TransactionFactory(
        pay_object=BookingFactory(status=Payable.Status.IN_PROGRESS),
        value=100,
        provider_fee=None,
        status=Transaction.Status.PENDING,
        provider_name=SquarePOS.name,
        provider_transaction_id="abc",
    )
    assert not payment.pay_object.status == Payable.Status.PAID

    with patch.object(
        SquarePOS,
        "get_checkout",
        return_value=checkout_return,
    ) as get_checkout_mock, patch.object(
        SquarePOS,
        "get_payment",
        return_value=Payment(
            status="COMPLETED",
            processing_fee=[{"amount_money": {"amount": -10, "currency": "GBP"}}],
        ),
    ) as get_payment_mock:
        payment.sync_transaction_with_provider()

        get_checkout_mock.assert_called_once_with("abc")
        get_payment_mock.assert_called_once_with("abc123")

        if expected_transaction_status == Transaction.Status.FAILED:
            assert not Transaction.objects.filter(id=payment.id).exists()
            return
        payment.refresh_from_db()
    assert payment.provider_fee == -10
    assert payment.status == expected_transaction_status
    assert payment.pay_object.status == expected_booking_status


@pytest.mark.django_db
def test_square_pos_sync_multiple_payment_ids():
    payment = TransactionFactory(
        pay_object=BookingFactory(status=Payable.Status.IN_PROGRESS),
        value=100,
        provider_fee=None,
        status=Transaction.Status.PENDING,
        provider_name=SquarePOS.name,
        provider_transaction_id="abc",
    )

    mock_response = TerminalCheckout(
        id="abc",
        status="COMPLETED",
        payment_ids=["abc123", "def123"],
        amount_money=Money(
            amount=100,
            currency="GBP",
        ),
        device_options=DeviceCheckoutOptions(
            device_id="abc",
            skip_receipt_screen=False,
        ),
    )

    with patch.object(
        SquarePOS,
        "get_checkout",
        return_value=mock_response,
    ) as get_checkout_mock, patch.object(
        SquarePOS,
        "get_payment",
        return_value=Payment(
            status="COMPLETED",
            processing_fee=[{"amount_money": {"amount": -10, "currency": "GBP"}}],
        ),
    ) as get_payment_mock:
        payment.sync_transaction_with_provider()

        get_checkout_mock.assert_called_once_with("abc")
        get_payment_mock.assert_any_call("abc123")
        get_payment_mock.assert_any_call("def123")
        assert get_payment_mock.call_count == 2

        payment.refresh_from_db()

    assert payment.provider_fee == -20
    assert payment.status == Transaction.Status.COMPLETED
    assert payment.pay_object.status == Payable.Status.PAID


@pytest.mark.django_db
def test_square_pos_sync_no_payments():
    payment = TransactionFactory(
        pay_object=BookingFactory(status=Payable.Status.IN_PROGRESS),
        value=100,
        provider_fee=None,
        status=Transaction.Status.PENDING,
        provider_name=SquarePOS.name,
        provider_transaction_id="abc",
    )

    mock_response = TerminalCheckout(
        id="abc",
        status="COMPLETED",
        payment_ids=["abc123", "def123"],
        amount_money=Money(
            amount=100,
            currency="GBP",
        ),
        device_options=DeviceCheckoutOptions(
            device_id="abc",
            skip_receipt_screen=False,
        ),
    )

    with patch.object(
        SquarePOS,
        "get_checkout",
        return_value=mock_response,
    ) as get_checkout_mock, patch.object(
        SquarePOS,
        "get_payment",
        return_value=None,
    ) as get_payment_mock:
        payment.sync_transaction_with_provider()

        get_checkout_mock.assert_called_once_with("abc")
        assert get_payment_mock.call_count == 2

        payment.refresh_from_db()

    assert payment.provider_fee is None
    assert payment.status == Transaction.Status.COMPLETED
    assert payment.pay_object.status == Payable.Status.PAID


@pytest.mark.django_db
def test_square_pos_sync_no_payment_fees():
    payment = TransactionFactory(
        pay_object=BookingFactory(status=Payable.Status.IN_PROGRESS),
        value=100,
        provider_fee=None,
        status=Transaction.Status.PENDING,
        provider_name=SquarePOS.name,
        provider_transaction_id="abc",
    )

    mock_response = TerminalCheckout(
        id="abc",
        status="COMPLETED",
        payment_ids=["abc123", "def123"],
        amount_money=Money(
            amount=100,
            currency="GBP",
        ),
        device_options=DeviceCheckoutOptions(
            device_id="abc",
            skip_receipt_screen=False,
        ),
    )

    with patch.object(
        SquarePOS,
        "get_checkout",
        return_value=mock_response,
    ) as get_checkout_mock, patch.object(
        SquarePOS,
        "get_payment",
        return_value=Payment(),
    ) as get_payment_mock:
        payment.sync_transaction_with_provider()

        get_checkout_mock.assert_called_once_with("abc")
        assert get_payment_mock.call_count == 2

        payment.refresh_from_db()

    assert payment.provider_fee is None
    assert payment.status == Transaction.Status.COMPLETED
    assert payment.pay_object.status == Payable.Status.PAID


@pytest.mark.django_db
def test_square_pos_sync_no_payment_id():
    payment = TransactionFactory(
        pay_object=BookingFactory(status=Payable.Status.IN_PROGRESS),
        value=100,
        provider_fee=None,
        status=Transaction.Status.PENDING,
        provider_name=SquarePOS.name,
        provider_transaction_id="abc",
    )

    mock_response = TerminalCheckout(
        id="abc",
        status="COMPLETED",
        amount_money=Money(
            amount=100,
            currency="GBP",
        ),
        device_options=DeviceCheckoutOptions(
            device_id="abc",
            skip_receipt_screen=False,
        ),
    )

    with patch.object(
        SquarePOS,
        "get_checkout",
        return_value=mock_response,
    ) as get_checkout_mock, patch.object(
        SquarePOS,
        "get_payment",
        return_value=Payment(
            status="COMPLETED",
            processing_fee=[{"amount_money": {"amount": -10, "currency": "GBP"}}],
        ),
    ) as get_payment_mock:
        payment.sync_transaction_with_provider()

        get_checkout_mock.assert_called_once_with("abc")
        assert get_payment_mock.call_count == 0

        payment.refresh_from_db()

    assert payment.provider_fee is None
    assert payment.status == Transaction.Status.COMPLETED
    assert payment.pay_object.status == Payable.Status.PAID


@pytest.mark.django_db
def test_square_pos_sync_no_terminal_id():
    payment = TransactionFactory(
        pay_object=BookingFactory(status=Payable.Status.IN_PROGRESS),
        value=100,
        provider_fee=None,
        status=Transaction.Status.PENDING,
        provider_name=SquarePOS.name,
        provider_transaction_id="abc",
    )

    mock_response = TerminalCheckout(
        status="FAILED",
        payment_ids=["abc123"],
        amount_money=Money(
            amount=100,
            currency="GBP",
        ),
        device_options=DeviceCheckoutOptions(
            device_id="abc",
            skip_receipt_screen=False,
        ),
    )

    with patch.object(
        SquarePOS,
        "get_checkout",
        return_value=mock_response,
    ), patch.object(
        SquarePOS,
        "get_payment",
        return_value=Payment(
            status="COMPLETED",
            processing_fee=[{"amount_money": {"amount": -10, "currency": "GBP"}}],
        ),
    ):
        with pytest.raises(PaymentException):
            payment.sync_transaction_with_provider()

        payment.refresh_from_db()

    assert payment.status == Transaction.Status.PENDING
    assert payment.pay_object.status == Payable.Status.IN_PROGRESS


@pytest.mark.django_db
def test_square_pos_sync_payment_no_checkout():
    payment = TransactionFactory(
        pay_object=BookingFactory(status=Payable.Status.IN_PROGRESS),
        value=100,
        provider_fee=None,
        status=Transaction.Status.PENDING,
        provider_name=SquarePOS.name,
        provider_transaction_id="abc",
    )

    with patch.object(
        SquarePOS,
        "get_checkout",
        return_value=None,
    ):
        with pytest.raises(PaymentException):
            payment.sync_transaction_with_provider()
            payment.refresh_from_db()

    assert payment.status == Transaction.Status.PENDING
    assert payment.pay_object.status == Payable.Status.IN_PROGRESS


###
# General Square
###


@pytest.mark.django_db
def test_square_get_payments_error(mock_square):
    with mock_square(
        SquareOnline.client.payments,
        "get",
        throw_default_exception=True,
    ):
        with pytest.raises(SquareException):
            SquareOnline.get_payment("abc")


@pytest.mark.django_db
def test_square_get_payment(mock_square):
    mock_response = GetPaymentResponse(
        payment={
            "id": "abc",
            "status": "COMPLETED",
            "processing_fee": [{"amount_money": {"amount": -10, "currency": "GBP"}}],
        }
    )

    with mock_square(SquareOnline.client.payments, "get", mock_response):
        assert SquareOnline.get_payment("abc") == Payment(
            id="abc",
            status="COMPLETED",
            processing_fee=[{"amount_money": {"amount": -10, "currency": "GBP"}}],
        )


@pytest.mark.parametrize(
    "body, signature, signature_key, webhook_url, valid",
    [
        (
            {
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
            },
            "xoa9/2fAXamuULrlhV1HP7C4ai4=",
            "Hd_mmQkhER3EPkpRpNQh9Q",
            "https://webhook.site/5bca8c49-e6f0-40ed-9415-4035bc05b48d",
            True,
        ),
        (
            {
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
                            "status": "NOTCOMPLETED",
                            "updated_at": "2020-04-10T14:44:06.039Z",
                        }
                    },
                },
            },
            "xoa9/2fAXamuULrlhV1HP7C4ai4=",
            "Hd_mmQkhER3EPkpRpNQh9Q",
            "https://webhook.site/5bca8c49-e6f0-40ed-9415-4035bc05b48d",
            False,
        ),
    ],
)
def test_is_valid_callback(body, signature, signature_key, webhook_url, valid):
    with patch.object(
        SquareWebhooks, "webhook_signature_key", new_callable=PropertyMock
    ) as key_mock, patch.object(
        SquareWebhooks, "webhook_url", new_callable=PropertyMock
    ) as url_mock:
        key_mock.return_value = signature_key
        url_mock.return_value = webhook_url
        assert SquareWebhooks.is_valid_callback(body, signature) == valid


###
# Manual PaymentMethods
###
@pytest.mark.django_db
@pytest.mark.parametrize(
    "payment_method, value, expected_method_str",
    [(Cash(), 10, "CASH"), (Card(), 0, "CARD")],
)
def test_manual_pay(payment_method, value, expected_method_str):
    booking = BookingFactory()
    payment = payment_method.pay(value, 12, booking)

    assert Transaction.objects.count() == 1
    assert Transaction.objects.first() == payment

    assert payment.pay_object == booking
    assert payment.value == value
    assert payment.currency == "GBP"
    assert payment.provider_name == expected_method_str
    assert payment.type == Transaction.Type.PAYMENT
    assert payment.app_fee == 12


@pytest.mark.django_db
def test_cash_cancel():
    transaction = TransactionFactory(provider_name=Cash.name)
    Cash.cancel(transaction)

    assert Transaction.objects.filter(
        pk=transaction.pk
    ).exists()  # Nothing should have happened


@pytest.mark.django_db
def test_cash_payment_sync():
    payment = TransactionFactory(provider_name=Cash.name)
    assert payment.sync_transaction_with_provider() is None


###
# General PaymentMethods
###


@pytest.mark.parametrize(
    "payment_method, is_refundable",
    [
        (Cash, False),
        (Card, True),
        (SquarePOS, False),
        (SquareOnline, True),
    ],
)
def test_is_refundable(payment_method, is_refundable):
    assert payment_method.is_refundable == is_refundable
