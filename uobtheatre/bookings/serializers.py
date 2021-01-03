import itertools

from rest_framework import serializers

from uobtheatre.bookings.models import (
    Booking,
    ConcessionType,
    Discount,
    DiscountRequirement,
    PercentageMiscCost,
    Ticket,
    ValueMiscCost,
)
from uobtheatre.productions.serializers import PerformanceSerializer
from uobtheatre.utils.serializers import AppendIdSerializerMixin, UserIdSerializer
from uobtheatre.venues.serializers import SeatGroupSerializer


class ConcessionTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConcessionType
        fields = ("id", "name", "description")


class CreateBookingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Booking
        fields = "__all__"


class MiscCostSerializer(serializers.ModelSerializer):
    class Meta:
        fields = ("name", "description")
        abstract = True


class ValueMiscCostSerializer(MiscCostSerializer):
    class Meta:
        model = ValueMiscCost
        fields = MiscCostSerializer.Meta.fields + ("value",)


class PercentageMiscCostSerializer(MiscCostSerializer):
    value = serializers.SerializerMethodField("get_value")

    class Meta:
        model = PercentageMiscCost
        fields = MiscCostSerializer.Meta.fields + (
            "percentage",
            "value",
        )

    def get_value(self, misc_cost):
        booking = self.context.get("booking", None)
        return misc_cost.value(booking) if booking else None


class BookingPriceBreakDownSerializer(serializers.ModelSerializer):
    tickets = serializers.SerializerMethodField("get_tickets")
    tickets_price = serializers.IntegerField()
    discounts_value = serializers.IntegerField(source="discount_value")
    misc_costs = serializers.SerializerMethodField("get_misc_costs")
    subtotal_price = serializers.IntegerField(source="subtotal")

    misc_costs_value = serializers.IntegerField()
    total_price = serializers.IntegerField(source="total")

    class Meta:
        model = Booking
        fields = (
            "tickets",
            "tickets_price",
            "discounts_value",
            "subtotal_price",
            "misc_costs",
            "misc_costs_value",
            "total_price",
        )

    def get_misc_costs(self, booking):
        return (
            PercentageMiscCostSerializer(
                PercentageMiscCost.objects.all(),
                many=True,
                context={"booking": booking},
            ).data
            + ValueMiscCostSerializer(
                ValueMiscCost.objects.all(),
                many=True,
                context={"booking": booking},
            ).data
        )

    def get_tickets(self, booking):
        groups = itertools.groupby(
            booking.tickets.order_by("pk"),
            lambda ticket: (ticket.seat_group, ticket.concession_type),
        )
        tickets = []
        for ticket_group, group in groups:
            number = len(list(group))
            price = booking.performance.price_with_concession(
                ticket_group[1],
                booking.performance.performance_seat_groups.get(
                    seat_group=ticket_group[0]
                ).price
                or 0,
            )
            tickets.append(
                {
                    "ticket_price": price,
                    "number": number,
                    "seat_group": SeatGroupSerializer(ticket_group[0]).data,
                    "concession_type": ConcessionTypeSerializer(ticket_group[1]).data,
                    "total_price": price * number,
                }
            )
        return tickets


class BookingListSerialiser(AppendIdSerializerMixin, serializers.ModelSerializer):
    """
    Booking serializers used
    """

    total_price = serializers.IntegerField(source="total")
    user_id = UserIdSerializer()
    performance = PerformanceSerializer()

    class Meta:
        model = Booking
        fields = (
            "id",
            "booking_reference",
            "performance",
            "total_price",
            "user_id",
            "status",
        )


class BookingSerialiser(AppendIdSerializerMixin, serializers.ModelSerializer):
    """ Booking serializer to create booking """

    performance = PerformanceSerializer()
    user_id = UserIdSerializer()
    price_breakdown = serializers.SerializerMethodField("get_price_break_down")

    class Meta:
        model = Booking
        fields = (
            "id",
            "user_id",
            "booking_reference",
            "performance",
            "price_breakdown",
            "user_id",
            "status",
        )

    def get_price_break_down(self, booking):
        serialized_price_breakdown = BookingPriceBreakDownSerializer(booking)
        return serialized_price_breakdown.data


class CreateTicketSerializer(AppendIdSerializerMixin, serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = (
            "seat_group",
            "concession_type",
        )


class CreateBookingSerialiser(AppendIdSerializerMixin, serializers.ModelSerializer):
    """ Booking serializer to create booking """

    tickets = CreateTicketSerializer(many=True, required=False)

    def create(self, validated_data):
        # Extract seating bookings from booking
        tickets = validated_data.pop("tickets")
        # Create the booking
        booking = Booking.objects.create(user=self.context["user"], **validated_data)

        # Create all the seat bookings
        for ticket in tickets:
            Ticket.objects.create(booking=booking, **ticket)

        return booking

    class Meta:
        model = Booking
        fields = ("id", "performance", "tickets")


class DiscountRequirementSerializer(serializers.ModelSerializer):
    concession_type = ConcessionTypeSerializer()

    class Meta:
        model = DiscountRequirement
        fields = ("number", "concession_type")


class DiscountSerializer(serializers.ModelSerializer):
    discount_requirements = DiscountRequirementSerializer(many=True)

    class Meta:
        model = Discount
        fields = ("name", "discount", "seat_group", "discount_requirements")
