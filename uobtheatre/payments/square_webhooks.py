import base64
import hmac
import json

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView
from square.types.payment import Payment
from square.types.payment_refund import PaymentRefund

from uobtheatre.bookings.models import Booking
from uobtheatre.payments.models import Transaction
from uobtheatre.payments.transaction_providers import SquarePOS
from uobtheatre.utils.utils import deep_get


class SquareWebhooks(APIView):
    """
    Handle square webhook
    """

    webhook_signature_key = settings.SQUARE_SETTINGS["SQUARE_WEBHOOK_SIGNATURE_KEY"]  # type: ignore
    webhook_url = f"{settings.BASE_URL}/{settings.SQUARE_SETTINGS['PATH']}"  # type: ignore

    @classmethod
    def is_valid_callback(cls, callback_body: dict, callback_signature: str) -> bool:
        """
        When square sends a webhook to the api, it is import to check the
        webhook is actually from square. This uses the provided square webhook
        secret to validate this requeset is from them.

        The secret is provided by the "SQUARE_WEBHOOK_SIGNATURE_KEY"
        environment varaible.

        Args:
            callback_body (dict): The body of the webhook
            callback_signature (str): The provided signature

        Returns:
            bool: True if the signature is valid and therefore the message is
                from square
        """

        # Combine your webhook notification URL and the JSON body of the
        # incoming request into a single string
        clean_request = json.dumps(callback_body, separators=(",", ":"))
        url_request_bytes = cls.webhook_url.encode("utf-8") + clean_request.encode(
            "utf-8"
        )

        # Generate the HMAC-SHA1 signature of the string, signed with the
        # webhook signature key
        hmac_code = hmac.new(
            key=cls.webhook_signature_key.encode("utf-8"),
            msg=None,
            digestmod="sha1",
        )
        hmac_code.update(url_request_bytes)
        generated_hash = hmac_code.digest()

        # Compare the generated signature with the signature included in the
        # request
        return hmac.compare_digest(
            base64.b64encode(generated_hash), callback_signature.encode("utf-8")
        )

    @classmethod
    def get_object_location_id(cls, object_data: dict) -> str | None:
        """Returns the string location ID found within the square webhook payload object"""
        object_types = ["checkout", "payment", "refund"]

        for object_type in object_types:
            if location_id := deep_get(object_data, f"{object_type}.location_id"):
                return location_id

        return None

    def post(self, request, **_):  # pylint: disable=too-many-return-statements
        """
        Endpoint for square webhooks
        """
        signature = request.META.get("HTTP_X_SQUARE_SIGNATURE", "")
        if not self.is_valid_callback(request.data, signature):
            return Response("Invalid signature", status=400)

        request_data = request.data
        try:
            if request_data["type"] == "terminal.checkout.updated":
                # This is a terminal checkout
                try:
                    Transaction.objects.get(
                        provider_transaction_id=request_data["data"]["object"][
                            "checkout"
                        ]["id"],
                        provider_name=SquarePOS.name,
                    ).sync_transaction_with_provider()
                except Transaction.DoesNotExist as exc:
                    if (
                        request_data["data"]["object"]["checkout"]["status"]
                        == "CANCELED"
                    ):
                        # If we can't find the transaction, and square is telling us it has been cancelled, we don't mind
                        return Response(status=201)
                    raise exc

            elif request_data["type"] == "payment.updated":
                # This is a payment update webhook
                square_payment = request_data["data"]["object"]["payment"]

                # First, check if this is a terminal checkout payment update. If it is, the data inside is for the payment not the checkout, so we don't use it
                provider_id = square_payment.get("terminal_checkout_id")
                data = None

                if not provider_id:
                    # Not a terminal checkout, therefore it is a standard payment
                    provider_id = square_payment["id"]
                    data = Payment(**square_payment)

                Transaction.objects.get(
                    provider_transaction_id=provider_id,
                ).sync_transaction_with_provider(data)

            elif request_data["type"] == "refund.updated":
                # This is a refund webhook
                square_refund = request_data["data"]["object"]["refund"]
                refund_data = PaymentRefund(**square_refund)

                transaction = Transaction.objects.get(
                    provider_transaction_id=request_data["data"]["id"],
                    type=Transaction.Type.REFUND,
                )

                transaction.sync_transaction_with_provider(refund_data)

                booking = Booking.objects.get(
                    transactions__provider_transaction_id=transaction.provider_transaction_id,
                )
                booking.status = Booking.Status.REFUNDED
                booking.save()
            else:
                return Response(status=202)
        except Transaction.DoesNotExist:
            # Check for the correct location
            if (
                not self.get_object_location_id(request_data["data"]["object"])
                == settings.SQUARE_SETTINGS["SQUARE_LOCATION"]
            ):
                return Response(status=203)

            return Response("Unknown Transaction", status=404)

        return Response(status=200)
