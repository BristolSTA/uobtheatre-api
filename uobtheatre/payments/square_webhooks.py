from rest_framework.response import Response
from rest_framework.views import APIView

from uobtheatre.payments.payment_methods import SquarePOS


class SquareWebhooks(APIView):
    """
    Handle square webhook
    """

    def post(self, request, **_):
        """
        Endpoint for square webhooks
        """
        signature = request.META.get("HTTP_X_SQUARE_SIGNATURE", "")
        try:
            SquarePOS.handle_webhook(request.data, signature)
            return Response(status=200)
        except ValueError as exe:
            return Response(str(exe), status=400)
