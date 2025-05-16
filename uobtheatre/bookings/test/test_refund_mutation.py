# pylint: disable=too-many-lines

import pytest
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm
from square.types.money import Money
from square.types.payment_refund import PaymentRefund
from square.types.refund_payment_response import RefundPaymentResponse

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.mutations import PayBooking
from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.payments.transaction_providers import SquareRefund
from uobtheatre.productions.test.factories import PerformanceFactory

# Helpers


def request_query(
    booking_reference,
    performance_id,
    preserve_payment_provider_fees=True,
    preserve_app_fees=False,
    refund_reason="unit tests",
    support_ticket_ref="1900",
):  # pylint: disable=too-many-arguments, too-many-positional-arguments, missing-function-docstring
    return """
        mutation {
            refundBooking(
                bookingReference: "%s"
                performance: "%s"
                preservePaymentProviderFees: %s
                preserveAppFees: %s
                refundReason: "%s"
                supportTicketRef: "%s"
            ) {
                success
                errors {
                    __typename
                    ... on NonFieldError {
                        message
                    }
                    ... on FieldError {
                        message
                    }
                }
                booking {
                    id
                    status
                }
            }
        }
    """ % (
        booking_reference,
        to_global_id("PerformanceNode", performance_id),
        "true" if preserve_payment_provider_fees else "false",
        "true" if preserve_app_fees else "false",
        refund_reason,
        support_ticket_ref,
    )


mock_response = RefundPaymentResponse(
    refund=PaymentRefund(
        id="abc",
        status="PENDING",
        amount_money=Money(
            amount=100,
            currency="GBP",
        ),
        payment_id="abc",
        order_id="nRDUxsrkGgorM3g8AT64kCLBLa4F",
        created_at="2021-12-30T10:40:54.672Z",
        updated_at="2021-12-30T10:40:54.672Z",
        location_id="LN9PN3P67S0QV",
    )
)


## Refund Booking Mutation


@pytest.mark.django_db
@pytest.mark.parametrize(
    "preserve_provider_fees,preserve_app_fees,refund_type",
    [
        (False, False, "Full"),
        (True, False, "Payment provider fee-accommodating"),
        (False, True, "Website fee-accommodating"),
        (True, True, "Payment provider and website fee-accommodating"),
    ],
)
def test_refund_booking(
    mock_square,
    mailoutbox,
    gql_client,
    preserve_provider_fees,
    preserve_app_fees,
    refund_type,
):  # pylint: disable=too-many-arguments, too-many-positional-arguments
    gql_client.login()
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance, status=Payable.Status.PAID, user=gql_client.user
    )
    TransactionFactory(pay_object=booking)

    assign_perm("bookings.refund_booking", gql_client.user)

    query = request_query(
        booking.reference,
        performance.id,
        preserve_provider_fees,
        preserve_app_fees,
        "unit tests",
        "1941",
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response,
    ):
        response = gql_client.execute(query)

    assert response == {
        "data": {
            "refundBooking": {
                "success": True,
                "errors": None,
                "booking": {
                    "id": to_global_id("BookingNode", booking.id),
                    "status": Payable.Status.REFUND_PROCESSING,
                },
            }
        }
    }

    booking.refresh_from_db()
    assert booking.status == Payable.Status.REFUND_PROCESSING
    assert booking.refunder == gql_client.user
    assert booking.refunded_at is not None
    assert booking.refund_reason == "unit tests"
    assert booking.refund_support_ticket == "1941"
    assert booking.is_locked

    assert len(mailoutbox) == 1
    assert (
        mailoutbox[0].subject
        == f"[UOBTheatre] {refund_type.title()} Booking Refunds Initiated"
    )


@pytest.mark.django_db
def test_refund_booking_no_permission(mock_square, gql_client):
    gql_client.login()
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance, status=Payable.Status.PAID, user=gql_client.user
    )
    TransactionFactory(pay_object=booking)

    query = request_query(
        booking.reference,
        performance.id,
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response,
    ):
        response = gql_client.execute(query)

    assert response == {
        "data": {
            "refundBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "You do not have permission to refund this booking.",
                    }
                ],
                "booking": None,
            }
        }
    }


@pytest.mark.django_db
def test_refund_non_superuser_must_provide_support_ticket(mock_square, gql_client):
    gql_client.login()
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance, status=Payable.Status.PAID, user=gql_client.user
    )
    TransactionFactory(pay_object=booking)

    assign_perm("bookings.refund_booking", gql_client.user)

    query = request_query(
        booking.reference,
        performance.id,
        support_ticket_ref="",
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response,
    ):
        response = gql_client.execute(query)

    assert response == {
        "data": {
            "refundBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "FieldError",
                        "message": "A support ticket reference is required for non-superusers.",
                    }
                ],
                "booking": None,
            }
        }
    }


@pytest.mark.django_db
def test_refund_booking_invalid_performance(mock_square, gql_client):
    gql_client.login()
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance, status=Payable.Status.PAID, user=gql_client.user
    )
    TransactionFactory(pay_object=booking)

    assign_perm("bookings.refund_booking", gql_client.user)

    query = request_query(booking.reference, "999")

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response,
    ):
        response = gql_client.execute(query)

    assert response == {
        "data": {
            "refundBooking": {
                "success": False,
                "errors": [
                    {"__typename": "NonFieldError", "message": "Object not found"}
                ],
                "booking": None,
            }
        }
    }


@pytest.mark.django_db
def test_refund_booking_invalid_booking(mock_square, gql_client):
    gql_client.login()
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance, status=Payable.Status.PAID, user=gql_client.user
    )
    TransactionFactory(pay_object=booking)

    assign_perm("bookings.refund_booking", gql_client.user)

    query = request_query(
        "INVALID_BOOKING_REFERENCE",
        performance.id,
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response,
    ):
        response = gql_client.execute(query)

    assert response == {
        "data": {
            "refundBooking": {
                "success": False,
                "errors": [
                    {"__typename": "NonFieldError", "message": "Object not found"}
                ],
                "booking": None,
            }
        }
    }


@pytest.mark.django_db
def test_refund_mismatched_booking_performance(mock_square, gql_client):
    gql_client.login()
    performance = PerformanceFactory()
    other_performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance, status=Payable.Status.PAID, user=gql_client.user
    )
    TransactionFactory(pay_object=booking)

    assign_perm("bookings.refund_booking", gql_client.user)

    query = request_query(
        booking.reference,
        other_performance.id,
        True,
        False,
        "unit tests",
        "1941",
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response,
    ):
        response = gql_client.execute(query)

    assert response == {
        "data": {
            "refundBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "FieldError",
                        "message": "The booking performance does not match the given performance.",
                    }
                ],
                "booking": None,
            }
        }
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status,success,expected_error",
    [
        (Payable.Status.PAID, True, None),
        (Payable.Status.CANCELLED, True, None),
        (
            Payable.Status.IN_PROGRESS,
            False,
            "can't be refunded due to its status (IN_PROGRESS)",
        ),
        (
            Payable.Status.REFUNDED,
            False,
            "can't be refunded due to its status (REFUNDED)",
        ),
        (
            Payable.Status.REFUND_PROCESSING,
            False,
            "can't be refunded because it is already being refunded",
        ),
    ],
)
def test_refund_booking_by_status(
    mock_square, gql_client, status, success, expected_error
):
    gql_client.login()
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance, status=status, user=gql_client.user
    )
    TransactionFactory(pay_object=booking)

    assign_perm("bookings.refund_booking", gql_client.user)

    query = request_query(
        booking.reference,
        performance.id,
        True,
        False,
        "unit tests",
        "1941",
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response,
    ):
        response = gql_client.execute(query)

    if success:
        assert response == {
            "data": {
                "refundBooking": {
                    "success": True,
                    "errors": None,
                    "booking": {
                        "id": to_global_id("BookingNode", booking.id),
                        "status": Payable.Status.REFUND_PROCESSING,
                    },
                }
            }
        }
    else:
        expected_message = "Booking (" + str(booking.reference) + ") " + expected_error
        assert response == {
            "data": {
                "refundBooking": {
                    "success": False,
                    "errors": [
                        {"__typename": "NonFieldError", "message": expected_message}
                    ],
                    "booking": None,
                }
            }
        }


@pytest.mark.django_db
def test_refund_booking_no_payment(mock_square, gql_client):
    gql_client.login()
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance, status=Payable.Status.PAID, user=gql_client.user
    )

    assign_perm("bookings.refund_booking", gql_client.user)

    query = request_query(
        booking.reference,
        performance.id,
        True,
        False,
        "unit tests",
        "1941",
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response,
    ):
        response = gql_client.execute(query)

    expected_message = (
        "Booking ("
        + str(booking.reference)
        + ") can't be refunded because it has no payments"
    )
    assert response == {
        "data": {
            "refundBooking": {
                "success": False,
                "errors": [
                    {"__typename": "NonFieldError", "message": expected_message}
                ],
                "booking": None,
            }
        }
    }


@pytest.mark.django_db
def test_refund_booking_locked(mock_square, gql_client):
    gql_client.login()
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance, status=Payable.Status.PAID, user=gql_client.user
    )
    TransactionFactory(pay_object=booking, status=Transaction.Status.PENDING)

    assign_perm("bookings.refund_booking", gql_client.user)

    query = request_query(
        booking.reference,
        performance.id,
        True,
        False,
        "unit tests",
        "1941",
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        mock_response,
    ):
        response = gql_client.execute(query)

    expected_message = (
        "Booking ("
        + str(booking.reference)
        + ") can't be refunded because it is locked"
    )
    assert response == {
        "data": {
            "refundBooking": {
                "success": False,
                "errors": [
                    {"__typename": "NonFieldError", "message": expected_message}
                ],
                "booking": None,
            }
        }
    }


@pytest.mark.django_db
def test_refunded_booking_square_error(mock_square, gql_client):
    gql_client.login()
    performance = PerformanceFactory()
    booking = BookingFactory(
        performance=performance, status=Payable.Status.PAID, user=gql_client.user
    )
    TransactionFactory(pay_object=booking)

    assign_perm("bookings.refund_booking", gql_client.user)

    query = request_query(
        booking.reference,
        performance.id,
        True,
        False,
        "unit tests",
        "1941",
    )

    with mock_square(
        SquareRefund.client.refunds,
        "refund_payment",
        throw_default_exception=True,
    ):
        response = gql_client.execute(query)

    assert response == {
        "data": {
            "refundBooking": {
                "success": False,
                "errors": [
                    {
                        "__typename": "NonFieldError",
                        "message": "('There was an issue processing your request (MY_CODE)', "
                        "400, None, None)",
                    }
                ],
                "booking": None,
            }
        }
    }
