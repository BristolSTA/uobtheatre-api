import base64
import hmac
import json

from django.conf import settings
from rest_framework.response import Response
from rest_framework.views import APIView

from uobtheatre.payments.models import Transaction
from uobtheatre.payments.transaction_providers import SquarePOS


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

    def post(self, request, **_):
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
                Transaction.objects.get(
                    provider_transaction_id=request_data["data"]["object"]["checkout"][
                        "id"
                    ],
                    provider_name=SquarePOS.name,
                ).sync_transaction_with_provider()

            elif request_data["type"] == "payment.updated":
                # This is a payment update webhook
                square_payment = request_data["data"]["object"]["payment"]

                # First, check if this is a terminal checkout payment update. If it is, the data inside is for the payment not the checkout, so we don't use it
                provider_id = square_payment.get("terminal_checkout_id")
                data = None

                if not provider_id:
                    # Not a terminal checkout, therefore it is a standard payment
                    provider_id = square_payment["id"]
                    data = square_payment

                Transaction.objects.get(
                    provider_transaction_id=provider_id,
                ).sync_transaction_with_provider(data)

            elif request_data["type"] == "refund.updated":
                Transaction.objects.get(
                    provider_transaction_id=request_data["data"]["id"],
                    type=Transaction.Type.REFUND,
                ).sync_transaction_with_provider(
                    request_data["data"]["object"]["refund"]
                )
            else:
                return Response(status=202)
        except Transaction.DoesNotExist:
            return Response("Unknown Transaction", status=404)

        return Response(status=200)
