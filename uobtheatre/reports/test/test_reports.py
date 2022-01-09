from datetime import datetime
from unittest.mock import patch

import pytest
from django.utils import timezone

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    PerformanceSeatingFactory,
    TicketFactory,
    ValueMiscCostFactory,
)
from uobtheatre.discounts.test.factories import (
    ConcessionTypeFactory,
    DiscountRequirementFactory,
)
from uobtheatre.payments import transaction_providers
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.payables import Payable
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.productions.models import Performance, Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.reports.reports import (
    DataSet,
    MetaItem,
    OutstandingSocietyPayments,
    PerformanceBookings,
    PeriodTotalsBreakdown,
    Report,
    get_option,
    require_option,
)
from uobtheatre.societies.models import Society
from uobtheatre.societies.test.factories import SocietyFactory
from uobtheatre.users.test.factories import UserFactory
from uobtheatre.utils.exceptions import GQLException
from uobtheatre.venues.test.factories import SeatGroupFactory


def create_fixtures():
    """Creates productions, bookings, and payment fixtures for the reports"""
    society_1 = SocietyFactory(name="Society 1")
    booking_1 = BookingFactory(
        performance=PerformanceFactory(
            production=ProductionFactory(
                name="Amazing Show 1",
                society=society_1,
                status=Production.Status.CLOSED,
            ),
            start=timezone.datetime(
                2021, 9, 23, 15, 0, tzinfo=timezone.get_current_timezone()
            ),
        ),
        user=UserFactory(first_name="Joe", last_name="Bloggs", email="joe@example.org"),
        reference="booking1",
    )  # This booking has 1 ticket, priced at 1000. With misc cost, this makes the total 1100.

    booking_2 = BookingFactory(
        performance=booking_1.performance,
        reference="booking2",
        user=UserFactory(
            first_name="Gill", last_name="Bloggs", email="gill@example.org"
        ),
    )  # This booking has 2 tickets, priced at 1000 each. With misc cost, this makes the total 2100. However, it lies outside of the time bounds for the period test

    booking_3 = BookingFactory(
        performance=PerformanceFactory(
            production=ProductionFactory(
                name="Amazing Show 2", society=SocietyFactory(name="Society 2")
            )
        ),
        reference="booking3",
    )  # This booking has 1 ticket, priced at 600 * 0.8 = 480. With misc cost, this makes the total 580.

    booking_4 = BookingFactory(
        admin_discount_percentage=1,
        performance=booking_3.performance,
        reference="booking4",
    )  # A comp booking. Total should be 0

    booking_5 = BookingFactory(
        performance=booking_1.performance,
        reference="booking5",
        status=Booking.PayableStatus.REFUNDED,
    )  # A refunded booking (of 1100 cost)

    BookingFactory(
        performance=booking_1.performance, status=Payable.PayableStatus.IN_PROGRESS
    )  # This booking is in progress - it shouldn't show in any reports

    discount_requirement = DiscountRequirementFactory()
    discount_requirement.discount.performances.add(booking_1.performance)
    discount_requirement.discount.performances.add(booking_3.performance)

    seat_group_1 = PerformanceSeatingFactory(
        performance=booking_1.performance,
        price=1000,
        seat_group=SeatGroupFactory(name="SeatGroup1"),
    ).seat_group
    seat_group_2 = PerformanceSeatingFactory(
        performance=booking_3.performance,
        seat_group=SeatGroupFactory(name="SeatGroup2"),
        price=600,
    ).seat_group

    ValueMiscCostFactory(value=100)

    concession_1 = ConcessionTypeFactory(name="ConessionType1")

    TicketFactory(
        booking=booking_1, seat_group=seat_group_1, concession_type=concession_1
    )
    TicketFactory(
        booking=booking_2, seat_group=seat_group_1, concession_type=concession_1
    )
    TicketFactory(
        booking=booking_2, seat_group=seat_group_1, concession_type=concession_1
    )
    TicketFactory(
        booking=booking_3,
        seat_group=seat_group_2,
        concession_type=discount_requirement.concession_type,
    )
    TicketFactory(
        booking=booking_4,
        seat_group=seat_group_2,
    )
    TicketFactory(
        booking=booking_5, seat_group=seat_group_1, concession_type=concession_1
    )

    payment_1 = TransactionFactory(
        pay_object=booking_1,
        value=booking_1.total,
        provider_name=transaction_providers.SquarePOS.name,
        provider_transaction_id="square_id",
        app_fee=booking_1.misc_costs_value(),
        provider_fee=10,
    )
    payment_1.created_at = "2021-09-08T00:00:01-00:00"
    payment_1.save()

    payment_2 = TransactionFactory(
        pay_object=booking_2,
        value=booking_2.total,
        provider_name=transaction_providers.Cash.name,
        app_fee=booking_2.misc_costs_value(),
    )
    payment_2.created_at = "2021-09-05T12:00:01-00:00"
    payment_2.save()

    payment_3 = TransactionFactory(
        pay_object=booking_3,
        value=booking_3.total,
    )
    payment_3.created_at = "2021-09-08T12:00:01-00:00"
    payment_3.save()

    payment_4 = TransactionFactory(
        pay_object=booking_5, value=booking_5.total, app_fee=5, provider_fee=2
    )
    payment_4.created_at = "2021-09-08T22:00:01-00:00"
    payment_4.save()

    refund_1 = TransactionFactory(
        pay_object=booking_5,
        value=-booking_5.total,
        provider_name=transaction_providers.SquareRefund.name,
        type=Transaction.Type.REFUND,
        app_fee=-5,
        provider_fee=-2,
    )
    refund_1.created_at = "2021-09-08T22:10:01-00:00"
    refund_1.save()

    # Create a pending payment (shouldn't show in reports)
    TransactionFactory(status=Transaction.Status.PENDING)

    return (payment_1, payment_2, payment_3, payment_4, refund_1)


def test_dataset_class():
    dataset = DataSet("My Dataset", ["Heading 1", "Heading 2"])

    assert len(dataset.data) == 0

    row = dataset.find_or_create_row_by_first_column(
        "My Unique ID", ["My Unique ID", "My value"]
    )
    assert len(dataset.data) == 1

    # Check it won't create a duplicate
    row_2 = dataset.find_or_create_row_by_first_column(
        "My Unique ID", ["My Unique ID", "My value"]
    )
    assert len(dataset.data) == 1
    assert row is row_2


def test_abstract_report():
    class SimpleReport(Report):
        pass

    report = SimpleReport()
    dataset = DataSet("My Dataset", ["1", "2"])
    report.datasets.append(dataset)
    report.meta.append(MetaItem("Name", "Value"))

    assert report.dataset_by_name("My Dataset") is dataset
    assert report.dataset_by_name("My Missing Dataset") is None

    assert report.get_meta_array() == [["Name", "Value"]]


def test_get_option():
    assert get_option([{"name": "MyName", "value": "MyValue"}], "MyName") == "MyValue"
    assert get_option([{"name": "MyName", "value": "MyValue"}], "MyOtherName") is None
    assert (
        get_option([{"name": "MyName", "value": "MyValue"}], "MyOtherName", "foo")
        == "foo"
    )


def test_require_option():
    options = [{"name": "MyName", "value": "MyValue"}]
    assert require_option(options, "MyName") is None

    with pytest.raises(GQLException) as exception:
        require_option(options, "MyOtherName")
        assert exception.message == "You must supply the MyOtherName option"


@pytest.mark.django_db
def test_period_totals_breakdown_report():
    (payment_1, _, payment_3, payment_4, refund_1) = create_fixtures()
    booking_1 = payment_1.pay_object
    booking_3 = payment_3.pay_object
    booking_5 = payment_4.pay_object

    # Generate report that covers this period
    with patch.object(Transaction, "sync_payments") as mock_sync:
        report = PeriodTotalsBreakdown(
            datetime.fromisoformat("2021-09-08T00:00:00"),
            datetime.fromisoformat("2021-09-08T23:00:00"),
        )

        mock_sync.assert_called_once()

    assert len(report.datasets) == 3

    assert len(report.meta) == 2
    assert report.meta[0].name == "No. of Payments"
    assert report.meta[0].value == "4"
    assert report.meta[1].name == "Total Income"
    assert report.meta[1].value == "1680"

    assert report.datasets[0].name == "Provider Totals"
    assert len(report.datasets[0].headings) == 2
    assert report.datasets[0].data == [
        ["SQUARE_ONLINE", 580 + 1100],
        ["SQUARE_POS", 1100],
        ["SQUARE_REFUND", -1100],
    ]

    assert report.datasets[1].name == "Production Totals"
    assert len(report.datasets[1].headings) == 3
    assert report.datasets[1].data == [
        [
            booking_1.performance.production.id,
            "Amazing Show 1",
            1100,
        ],
        [
            booking_3.performance.production.id,
            "Amazing Show 2",
            580,
        ],
    ]

    assert report.datasets[2].name == "Payments"
    assert len(report.datasets[2].headings) == 10
    assert report.datasets[2].data == [
        [
            str(payment_1.id),
            "2021-09-08 00:00:01",
            "PAYMENT",
            str(booking_1.id),
            "Booking",
            str(booking_1.performance.production.id),
            "Amazing Show 1",
            "1100",
            "SQUARE_POS",
            "square_id",
        ],
        [
            str(payment_3.id),
            "2021-09-08 12:00:01",
            "PAYMENT",
            str(booking_3.id),
            "Booking",
            str(booking_3.performance.production.id),
            "Amazing Show 2",
            "580",
            "SQUARE_ONLINE",
            payment_3.provider_transaction_id,
        ],
        [
            str(payment_4.id),
            "2021-09-08 22:00:01",
            "PAYMENT",
            str(booking_5.id),
            "Booking",
            str(booking_5.performance.production.id),
            "Amazing Show 1",
            "1100",
            "SQUARE_ONLINE",
            payment_4.provider_transaction_id,
        ],
        [
            str(refund_1.id),
            "2021-09-08 22:10:01",
            "REFUND",
            str(booking_5.id),
            "Booking",
            str(booking_5.performance.production.id),
            "Amazing Show 1",
            "-1100",
            "SQUARE_REFUND",
            refund_1.provider_transaction_id,
        ],
    ]


@pytest.mark.django_db
def test_outstanding_society_payments_report():
    create_fixtures()
    society_1 = Society.objects.all()[0]
    production_1 = Production.objects.all()[0]
    # NB: As production 2 is not "closed", it shouldn't show in this report
    with patch.object(Transaction, "sync_payments") as mock_sync:
        report = OutstandingSocietyPayments()

    mock_sync.assert_called_once()

    assert len(report.datasets) == 2

    assert len(report.meta) == 1
    assert report.meta[0].name == "Total Outstanding"
    assert report.meta[0].value == "1090"

    assert report.datasets[0].name == "Societies"
    assert len(report.datasets[0].headings) == 3
    assert report.datasets[0].data == [
        [
            society_1.id,
            "Society 1",
            900,
        ],
        [
            "",
            "Stage Technicians' Association",
            190,
        ],  # Our fee
    ]

    assert report.datasets[1].name == "Productions"
    assert len(report.datasets[1].headings) == 13
    assert report.datasets[1].data == [
        [
            production_1.id,
            "Amazing Show 1",
            society_1.id,
            "Society 1",
            4300,  # Payments total (2200 + 2100)
            2200,  # Of which card: 1100*2
            -1100,  # Refunds total
            -1100,  # Of which card
            3200,  # Net income
            1100,  # Net Card income
            10,  # Square fees
            190,  # Total misc costs (2 bookings * 100) - square fee
            900,  # Society transfer amount: Card payments (1100) - Total Misc costs (200)
        ]
    ]


@pytest.mark.django_db
def test_outstanding_society_payments_report_production_no_society():
    ProductionFactory(id=1, status=Production.Status.CLOSED, society=None)

    with patch.object(Transaction, "sync_payments"):
        with pytest.raises(Exception) as exception:
            OutstandingSocietyPayments()
            assert exception.value == "Production 1 has no society"


@pytest.mark.django_db
def test_performance_bookings_report():
    create_fixtures()

    performance_1 = Performance.objects.first()

    report = PerformanceBookings(performance_1)

    assert len(report.datasets) == 1

    assert len(report.meta) == 1
    assert report.meta[0].name == "Performance"
    assert (
        report.meta[0].value == "Performance of Amazing Show 1 at 15:00 on 23/09/2021"
    )

    assert report.datasets[0].name == "Bookings"
    assert len(report.datasets[0].headings) == 6
    assert report.datasets[0].data == [
        [
            Booking.objects.first().id,
            "booking1",
            "Joe Bloggs",
            "joe@example.org",
            "SeatGroup1 | ConessionType1",
            "1100",
        ],
        [
            Booking.objects.first().id + 1,
            "booking2",
            "Gill Bloggs",
            "gill@example.org",
            "SeatGroup1 | ConessionType1\r\nSeatGroup1 | ConessionType1",
            "2100",
        ],
    ]
