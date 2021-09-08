from datetime import datetime

import pytest

from uobtheatre.bookings.models import Booking
from uobtheatre.bookings.test.factories import (
    BookingFactory,
    PerformanceSeatingFactory,
    TicketFactory,
    ValueMiscCostFactory,
)
from uobtheatre.discounts.test.factories import DiscountRequirementFactory
from uobtheatre.payments import payment_methods
from uobtheatre.payments.models import Payment
from uobtheatre.payments.test.factories import PaymentFactory
from uobtheatre.productions.models import Production
from uobtheatre.productions.test.factories import PerformanceFactory, ProductionFactory
from uobtheatre.reports.reports import OutstandingSocietyPayments, PeriodTotalsBreakdown
from uobtheatre.societies.models import Society
from uobtheatre.societies.test.factories import SocietyFactory


def create_fixtures():
    """Creates productions, bookings, and payment fixtures for the reports"""
    booking_1 = BookingFactory(
        performance=PerformanceFactory(
            production=ProductionFactory(
                name="Amazing Show 1",
                society=SocietyFactory(name="Society 1"),
                status=Production.Status.CLOSED,
            )
        )
    )  # This booking has 1 ticket, priced at 1000. With misc cost, this makes the total 1100.

    booking_2 = BookingFactory(
        performance=booking_1.performance
    )  # This booking has 2 tickets, priced at 1000 each. With misc cost, this makes the total 2100. However, it lies outside of the time bounds

    booking_3 = BookingFactory(
        performance=PerformanceFactory(
            production=ProductionFactory(
                name="Amazing Show 2", society=SocietyFactory(name="Society 2")
            )
        )
    )  # This booking has 1 ticket, priced at 600 * 0.8 = 480. With misc cost, this makes the total 580.

    booking_4 = BookingFactory(
        admin_discount_percentage=1, performance=booking_3.performance
    )  # A comp booking. Total should be 0

    discount_requirement = DiscountRequirementFactory()
    discount_requirement.discount.performances.add(booking_1.performance)
    discount_requirement.discount.performances.add(booking_3.performance)

    seat_group_1 = PerformanceSeatingFactory(
        performance=booking_1.performance, price=1000
    ).seat_group
    seat_group_2 = PerformanceSeatingFactory(
        performance=booking_3.performance,
        price=600,
    ).seat_group

    ValueMiscCostFactory(value=100)

    TicketFactory(booking=booking_1, seat_group=seat_group_1)
    TicketFactory(booking=booking_2, seat_group=seat_group_1)
    TicketFactory(booking=booking_2, seat_group=seat_group_1)
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
    )
    payment_1.created_at = "2021-09-08T00:00:01"
    payment_1.save()

    payment_2 = PaymentFactory(pay_object=booking_2, value=booking_2.total())
    payment_2.created_at = "2021-09-05T12:00:01"
    payment_2.save()

    payment_3 = PaymentFactory(pay_object=booking_3, value=booking_3.total())
    payment_3.created_at = "2021-09-08T12:00:01"
    payment_3.save()


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

    assert report.datasets[0].name == "Provider Totals"
    assert len(report.datasets[0].headings) == 2
    assert report.datasets[0].data == [["SquarePOS", 1100], ["SquareOnline", 580]]

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
    assert len(report.datasets[2].headings) == 4
    assert report.datasets[2].data == [
        [
            payment_1.id,
            "2021-09-08 00:00:01",
            booking_1.id,
            1100,
        ],
        [
            payment_3.id,
            "2021-09-08 12:00:01",
            booking_3.id,
            580,
        ],
    ]


@pytest.mark.django_db
def test_outstanding_society_payments_report():
    create_fixtures()
    society_1 = Society.objects.all()[0]
    production_1 = Production.objects.all()[0]
    # NB: As production 2 is not "closed", it shouldn't show in this report

    report = OutstandingSocietyPayments()

    assert len(report.datasets) == 2

    assert report.datasets[0].name == "Societies"
    assert len(report.datasets[0].headings) == 3
    assert report.datasets[0].data == [
        [society_1.id, "Society 1", 3000],  # 3200 - 200 (misc cost),
        [
            "",
            "Stage Technicians' Association",
            200,
        ],  # Our fee
    ]

    assert report.datasets[1].name == "Productions"
    assert len(report.datasets[1].headings) == 6
    assert report.datasets[1].data == [
        [production_1.id, "Amazing Show 1", society_1.id, "Society 1", 3000, 200]
    ]
