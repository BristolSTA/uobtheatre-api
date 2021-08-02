import hmac

from rest_framework.response import Response
from rest_framework.views import APIView

from config.settings.common import BASE_URL, SQUARE_SETTINGS
from uobtheatre.bookings.models import Booking
from uobtheatre.payments.models import Payment


class SquareWebhooks(APIView):
    """
    Handle square webhook
    """

    def is_valid_callback(self, callback_body, callback_signature):
        # Combine your webhook notification URL and the JSON body of the incoming request into a single string
        square_path = f"{BASE_URL}/{SQUARE_SETTINGS['PATH']}"
        string_to_sign = square_path + callback_body

        # Generate the HMAC-SHA1 signature of the string, signed with your webhook signature key
        string_signature = (
            hmac.new(
                key=SQUARE_SETTINGS["SQUARE_WEBHOOK_SIGNATURE_KEY"],
                msg=string_to_sign,
                digestmod="sha1",
            )
            .digest()
            .encode("base64")
        )

        # Remove the trailing newline from the generated signature (this is a quirk of the Python library)
        string_signature = string_signature.rstrip("\n")

        # Compare your generated signature with the signature included in the request
        return hmac.compare_digest(string_signature, callback_signature)

    def post(self, request, format=None):
        if request.data["type"] == "terminal.checkout.updated":
            data = request.data["data"]
            if data["type"] == "checkout.event":
                checkout = data["object"]["checkout"]
                reference_id = checkout["reference_id"]

                booking = Booking.objects.get(reference=reference_id)
                Payment.objects.create(
                    pay_object=booking,
                    provider=Payment.PaymentProvider.SQUARE_POS,
                    type=Payment.PaymentType.PURCHASE,
                    provider_payment_id=checkout["payment_ids"][0],
                    value=checkout["amount_money"]["amount"],
                    currency=checkout["amount_money"]["currency"],
                )
                booking.status = Booking.BookingStatus.PAID
                booking.save()

        return Response(status=200)
