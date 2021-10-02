from datetime import datetime

import pytest

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
from uobtheatre.payments import payment_methods
from uobtheatre.payments.models import Payment
from uobtheatre.payments.test.factories import PaymentFactory
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
    booking_1 = BookingFactory(
        performance=PerformanceFactory(
            production=ProductionFactory(
                name="Amazing Show 1",
                society=SocietyFactory(name="Society 1"),
                status=Production.Status.CLOSED,
            ),
            start=datetime(2021, 9, 23, 15, 0),
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

    BookingFactory(
        performance=booking_1.performance, status=Booking.BookingStatus.IN_PROGRESS
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

    payment_1 = PaymentFactory(
        pay_object=booking_1,
        value=booking_1.total(),
        provider=payment_methods.SquarePOS.__name__,
        provider_payment_id="square_id",
    )
    payment_1.created_at = "2021-09-08T00:00:01"
    payment_1.save()

    payment_2 = PaymentFactory(
        pay_object=booking_2, value=booking_2.total(), provider="CASH"
    )
    payment_2.created_at = "2021-09-05T12:00:01"
    payment_2.save()

    payment_3 = PaymentFactory(pay_object=booking_3, value=booking_3.total())
    payment_3.created_at = "2021-09-08T12:00:01"
    payment_3.save()


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
    create_fixtures()
    booking_1 = Booking.objects.all()[0]
    booking_3 = Booking.objects.all()[2]
    payment_1 = Payment.objects.all()[0]
    payment_3 = Payment.objects.all()[2]

    # Generate report that covers this period
    report = PeriodTotalsBreakdown(
        datetime.fromisoformat("2021-09-08T00:00:00"),
        datetime.fromisoformat("2021-09-08T23:00:00"),
    )

    assert len(report.datasets) == 3

    assert len(report.meta) == 2
    assert report.meta[0].name == "No. of Payments"
    assert report.meta[0].value == "2"
    assert report.meta[1].name == "Total Income"
    assert report.meta[1].value == "1680"

    assert report.datasets[0].name == "Provider Totals"
    assert len(report.datasets[0].headings) == 2
    assert report.datasets[0].data == [
        ["SquarePOS", 1100],
        ["SQUARE_ONLINE", 580],
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
    assert len(report.datasets[2].headings) == 6
    assert report.datasets[2].data == [
        [
            str(payment_1.id),
            "2021-09-08 00:00:01",
            str(booking_1.id),
            "1100",
            "SquarePOS",
            "square_id",
        ],
        [
            str(payment_3.id),
            "2021-09-08 12:00:01",
            str(booking_3.id),
            "580",
            "SQUARE_ONLINE",
            "",
        ],
    ]


@pytest.mark.django_db
def test_outstanding_society_payments_report_without_misc_cost():
    create_fixtures()
    society_1 = Society.objects.all()[0]
    production_1 = Production.objects.all()[0]
    # NB: As production 2 is not "closed", it shouldn't show in this report
    print(production_1.sales_breakdown())
    report = OutstandingSocietyPayments()

    assert len(report.datasets) == 2

    assert len(report.meta) == 1
    assert report.meta[0].name == "Total Outstanding"
    assert report.meta[0].value == "1100"

    assert report.datasets[0].name == "Societies"
    assert len(report.datasets[0].headings) == 3
    assert report.datasets[0].data == [
        [
            society_1.id,
            "Society 1",
            1100,
        ],
        [
            "",
            "Stage Technicians' Association",
            0,
        ],  # Our fee
    ]

    assert report.datasets[1].name == "Productions"
    assert len(report.datasets[1].headings) == 8
    assert report.datasets[1].data == [
        [
            production_1.id,
            "Amazing Show 1",
            society_1.id,
            "Society 1",
            3200,  # Payments total (1100 + 2100)
            1100,  # Of which card: 1100
            0,  # Total misc costs (2 bookings * 100)
            1100,  # Card payments (1100) - Total Misc costs (200)
        ]
    ]


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
