import re
from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.exceptions import CantBeRefundedException
from uobtheatre.payments.tasks import RefundTask, refund_payable, refund_payment
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.productions.test.factories import ProductionFactory
from uobtheatre.users.test.factories import UserFactory


@pytest.mark.parametrize(
    "exception,makes_skipped",
    [(CantBeRefundedException(), True), (ValueError(), False)],
)
def test_base_refund_task_on_failure(exception, makes_skipped):
    instance = RefundTask()

    with patch.object(instance, "update_state") as mock:
        instance.on_failure(exception, "1234", tuple(), {}, None)

    if makes_skipped:
        mock.assert_called_once_with(state="SKIPPED")
    else:
        mock.assert_not_called()


@pytest.mark.django_db
def test_refund_payment_task():
    transaction = TransactionFactory(id=123)
    with patch("uobtheatre.payments.models.Transaction.refund", autospec=True) as mock:
        refund_payment(123)
    mock.assert_called_once_with(transaction)


@pytest.mark.django_db
def test_refund_payable_task():
    booking = BookingFactory(id=123)
    auth_user = UserFactory()
    with patch("uobtheatre.bookings.models.Booking.refund", autospec=True) as mock:
        refund_payable(123, booking.content_type.pk, auth_user.pk)
    mock.assert_called_once_with(booking, auth_user, send_admin_email=False)


@pytest.mark.django_db
def test_refund_payable_task_non_payable():
    production = ProductionFactory()
    auth_user = UserFactory()
    with pytest.raises(
        ValueError,
        match=re.escape(
            "Object found, but object is not a payable object (Production)"
        ),
    ):
        refund_payable(production.pk, production.content_type.pk, auth_user.pk)


@pytest.mark.django_db
def test_refund_payable_task_invalid_content_type():
    content_type = ContentType.objects.create()
    auth_user = UserFactory()
    with pytest.raises(
        ValueError,
        match=re.escape(
            f"No matching model exists for specified content type (Type ID: {content_type.pk})"
        ),
    ):
        refund_payable(1, content_type.pk, auth_user.pk)
