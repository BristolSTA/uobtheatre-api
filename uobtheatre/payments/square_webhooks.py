from rest_framework.response import Response
from rest_framework.views import APIView

from uobtheatre.bookings.models import Booking
from uobtheatre.payments.payment_methods import SquarePOS


class SquareWebhooks(APIView):
    """
    Handle square webhook
    """

    def post(self, request, **_):
        """
        Endpoint for square webhooks
        """
        signature = request.get_header("X-Square-Signature", default="")

        if not SquarePOS.is_valid_callback(request.data, signature):
            return Response(data="Invalid square webhhok signature.", status=401)

        if request.data["type"] == "terminal.checkout.updated":
            event_data = request.data["data"]
            if event_data["type"] == "checkout.event":
                reference_id = event_data["object"]["checkout"]["reference_id"]
                booking = Booking.objects.get(reference=reference_id)
                SquarePOS.handle_checkout_event(event_data, booking)
                booking.status = Booking.BookingStatus.PAID
                booking.save()

        return Response(status=200)
