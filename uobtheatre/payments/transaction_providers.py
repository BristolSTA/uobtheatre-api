import abc
import re
from typing import TYPE_CHECKING, Any, Dict, Literal, Optional, Sequence, Type, Union
from uuid import uuid4

from django.conf import settings
from square import Square as Client
from square.core.api_error import ApiError
from square.requests.device_checkout_options import (
    DeviceCheckoutOptionsParams as DeviceCheckoutOptions,
)
from square.requests.location import LocationParams
from square.requests.money import MoneyParams
from square.requests.terminal_checkout import TerminalCheckoutParams
from square.types.device import Device
from square.types.device_code import DeviceCode
from square.types.location import Location
from square.types.payment import Payment
from square.types.payment_refund import PaymentRefund
from square.types.terminal_checkout import TerminalCheckout

from uobtheatre.payments import models as payment_models
from uobtheatre.utils.exceptions import PaymentException, SquareException
from uobtheatre.utils.models import classproperty

if TYPE_CHECKING:
    from uobtheatre.payments.payables import Payable


class TransactionProvider(abc.ABC):
    """
    Absctact class for transactions methods. This includes both refunds and
    payments.
    """

    name: str

    def __init_subclass__(cls) -> None:
        cls.name = TransactionProvider.generate_name(cls.__name__)

    @classmethod
    @classproperty
    def __all__(cls) -> Sequence[Type["TransactionProvider"]]:
        return PaymentProvider.__all__ + RefundProvider.__all__  # type: ignore

    @classmethod
    @classproperty
    @abc.abstractmethod
    def description(cls):
        pass

    @staticmethod
    def generate_name(name):
        name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
        name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)
        name = name.replace("-", "_")
        return name.upper()

    @classmethod
    @classproperty
    def choices(cls):
        choices = [(method.name, method.name) for method in cls.__all__]  # type: ignore[attr-defined]
        return choices

    @classmethod
    def create_payment_object(
        cls, pay_object: "Payable", value: int, app_fee, **kwargs
    ) -> "payment_models.Transaction":
        return payment_models.Transaction.objects.create(
            provider_name=cls.name,
            pay_object=pay_object,
            value=value,
            app_fee=app_fee,
            **kwargs,
        )

    @classmethod
    def sync_transaction(
        cls, payment: "payment_models.Transaction", data: Optional[dict] = None
    ):
        """Syncs the refund payment from the provider"""

    @classmethod
    def cancel(
        cls, payment: "payment_models.Transaction"  # pylint: disable=unused-argument
    ):
        """Cancel the payment

        Most payment methods cannot be cancelled (as they will never be
        pending) so the default implementation is just to return.
        """
        return

    @classmethod
    def get_payment_provider_id(cls, payment: "payment_models.Transaction") -> str:
        """Get the ID of the provided payment assigned by the provider"""
        if not payment.provider_transaction_id:
            raise PaymentException("Payment has no provider_transaction_id")
        return payment.provider_transaction_id


class RefundProvider(TransactionProvider, abc.ABC):
    """
    Abscract class for all refund methods.
    """

    __all__: Sequence[Type["RefundProvider"]] = []  # type: ignore

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.__all__ = cls.__all__.append(cls)  # type: ignore #pylint: disable=assignment-from-no-return

    @classmethod
    @classproperty
    @abc.abstractmethod
    def is_automatic(cls) -> bool:
        """
        This determines wether the refund method can be used without any
        interaction from the uob team.
        """

    @classmethod
    def create_payment_object(cls, *args, **kwargs) -> "payment_models.Transaction":
        kwargs["type"] = payment_models.Transaction.Type.REFUND
        return super().create_payment_object(*args, **kwargs)


class PaymentProvider(TransactionProvider, abc.ABC):
    """
    Abstract class for all payment methods.

    Every payment method should define a `pay` method. This will take a value
    and the the object being payed for and return (and save) a payment object
    if the payment is completed.

    Whenever a payment method is created it is automatically added to the
    __all__ attirbute of PaymentMethod. This will therefore add it to the
    choices field and the graphene enum.

    If the payment method has refund_methods it can be refunded.
    These are the methods that can be used to refund payments created with this
    payment method.
    """

    __all__: Sequence[Type["PaymentProvider"]] = []  # type: ignore

    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls.__all__.append(cls)  # type: ignore

    @abc.abstractmethod
    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Transaction":
        raise NotImplementedError

    @classmethod
    def create_payment_object(cls, *args, **kwargs) -> "payment_models.Transaction":
        kwargs["type"] = payment_models.Transaction.Type.PAYMENT
        return super().create_payment_object(*args, **kwargs)

    @classmethod
    @classproperty
    def refund_providers(cls) -> tuple[RefundProvider, ...]:
        """A tuple of methods that can be used to refund payments"""
        return tuple()

    @classmethod
    @classproperty
    def is_refundable(cls) -> bool:
        return bool(cls.refund_providers)

    @classmethod
    def is_valid_refund_provider(cls, provider: RefundProvider) -> bool:
        return type(provider) in set(
            type(provider) for provider in cls.refund_providers  # type: ignore
        )

    @classmethod
    @classproperty
    def automatic_refund_provider(cls) -> Optional[RefundProvider]:
        """
        Return the first payment method that can be used automatically. This
        means it can be used to refund the payment method without any
        interaction from the uob team.
        """
        return next(
            (method for method in cls.refund_providers if method.is_automatic), None  # type: ignore
        )

    @classmethod
    @classproperty
    def is_auto_refundable(cls) -> bool:
        """
        Returns whether this payment method has an automatic refund method.
        """
        return cls.automatic_refund_provider is not None


class SquareAPIMixin(abc.ABC):
    """Mixin that inserts square API client and handlers"""

    kwargs = {
        "version": "2025-04-16",
        "token": settings.SQUARE_SETTINGS["SQUARE_ACCESS_TOKEN"],  # type: ignore
        "environment": settings.SQUARE_SETTINGS["SQUARE_ENVIRONMENT"],  # type: ignore
    }

    if square_url := settings.SQUARE_SETTINGS["SQUARE_URL"]:  # pragma: no cover
        kwargs["base_url"] = square_url

    client = Client(**kwargs)

    @classmethod
    def _square_transaction_processing_fee(
        cls, square_object: Union[PaymentRefund, Payment]
    ) -> Optional[int]:
        """
        Get processing fee from a square transaction object dict.

        Args:
            square_object (PaymentRefund): Square object from square.

        Returns:
            int: Processing fee for payment
        """
        # If the processing fee has not be added to the payment
        if not square_object.processing_fee:
            return None

        return sum(
            fee.amount_money.amount
            for fee in square_object.processing_fee
            if fee.amount_money and fee.amount_money.amount
        )

    @classmethod
    def _fill_payment_from_square_response_object(
        cls, payment, response_object: Union[Payment, PaymentRefund]
    ):
        """Updates and fills a payment model from a refund response object"""
        if not response_object.status:
            raise PaymentException(
                f"Transaction failed to sync after refund for payment {payment.pay_object.payment_reference_id}"
            )

        payment.status = payment_models.Transaction.Status.from_square_status(
            response_object.status
        )
        if processing_fees := cls._square_transaction_processing_fee(response_object):
            payment.provider_fee = processing_fees
        return payment


class SquarePaymentMethod(SquareAPIMixin, abc.ABC):
    """
    Mixin for SquarePayment method classes which adds client and helper
    function. Sub-classes should import this mixin and the main PaymentMethod
    class.
    """

    @classmethod
    def get_payment(cls, payment_id: str) -> Payment | None:
        """Get full payment info from square for a given payment id.

        Args:
            payment_id (str): The id of the payment to be fetched

        Returns:
            dict: Payment response from square

        Raises:
            SquareException: When response is not successful
        """
        try:
            response = cls.client.payments.get(payment_id)

        except ApiError as error:
            raise SquareException(error) from error

        return response.payment


class ManualCardRefund(RefundProvider):
    """
    Refund method for refunding square payments.
    """

    description = "Manually refund"
    is_automatic = False  # type: ignore

    def refund(
        self,
        payment: "payment_models.Transaction",
        custom_refund_amount: Optional[int] = None,
    ):
        """
        Refund payment using square refund api, then create a new payment object
        with the refund amount.

        Args:
            payment (Payment): The payment to be refunded
            custom_refund_amount (int): The amount to be refunded. If not
                provided the full amount will be refunded.
        """
        if custom_refund_amount and custom_refund_amount > payment.value:
            raise PaymentException("Refund amount is greater than payment amount")

        refund_amount = (
            custom_refund_amount if custom_refund_amount is not None else payment.value
        )

        app_fee_reduction = None

        if payment.app_fee:
            print(payment.app_fee)
            # If the refund amount is less than the total amount minus the app fee, leave the app fee as is
            # Otherwise, reduce the app fee by whatever is needed to make the numbers add up
            # Thereby ensuring that we keep an amount to cover fees
            remaining_app_fee = payment.app_fee
            if (payment.value - refund_amount) < payment.app_fee:
                remaining_app_fee = payment.value - refund_amount

            app_fee_reduction = payment.app_fee - remaining_app_fee

        self.create_payment_object(
            payment.pay_object,
            -refund_amount,
            -app_fee_reduction if app_fee_reduction is not None else None,
            provider_fee=-payment.provider_fee if payment.provider_fee else None,
            status=payment_models.Transaction.Status.COMPLETED,
        )


class SquareRefund(RefundProvider, SquareAPIMixin):
    """
    Refund method for refunding square payments.
    """

    description = "Square refund"
    is_automatic = True  # type: ignore

    def __init__(self, idempotency_key: str):
        self.idempotency_key = idempotency_key

    def refund(
        self,
        payment: "payment_models.Transaction",
        custom_refund_amount: Optional[int] = None,
    ):
        """
        Refund payment using square refund api
        """
        if custom_refund_amount and custom_refund_amount > payment.value:
            raise PaymentException("Refund amount is greater than payment amount")

        refund_amount = (
            custom_refund_amount if custom_refund_amount is not None else payment.value
        )

        try:
            response = self.client.refunds.refund_payment(
                idempotency_key=self.idempotency_key,
                payment_id=payment.provider_transaction_id,
                amount_money=MoneyParams(
                    amount=refund_amount,
                    currency=payment.currency,
                ),
                reason=f"Refund for {payment.pay_object.payment_reference_id}",
            )

        except ApiError as error:
            raise SquareException(error) from error

        if not response.refund:
            if response.errors:
                raise PaymentException(
                    f"Refund failed for {payment.pay_object.payment_reference_id}: {response.errors[0].detail}"
                )

            raise PaymentException(
                f"Refund failed for {payment.pay_object.payment_reference_id}"
            )

        square_refund_details = response.refund.amount_money
        square_refund_amount = square_refund_details.amount
        square_refund_id = response.refund.id

        if not square_refund_id or not square_refund_amount:
            if response.errors:
                raise PaymentException(
                    f"Refund failed for {payment.pay_object.payment_reference_id}: {response.errors[0].detail}"
                )

            raise PaymentException(
                f"Refund failed for {payment.pay_object.payment_reference_id}"
            )

        app_fee_reduction = None

        if payment.app_fee:
            # If the refund amount is less than the total amount minus the app fee, leave the app fee as is
            # Otherwise, reduce the app fee by whatever is needed to make the numbers add up
            # Thereby ensuring that we keep fees to cover Square transaction costs
            remaining_app_fee = payment.app_fee
            if (payment.value - square_refund_amount) < payment.app_fee:
                remaining_app_fee = payment.value - square_refund_amount

            app_fee_reduction = payment.app_fee - remaining_app_fee

        self.create_payment_object(
            payment.pay_object,
            -square_refund_amount,
            -app_fee_reduction if app_fee_reduction is not None else None,
            provider_transaction_id=square_refund_id,
            currency=square_refund_details.currency,
            status=payment_models.Transaction.Status.PENDING,
        )

    @classmethod
    def sync_transaction(
        cls, payment: "payment_models.Transaction", data: Optional[PaymentRefund] = None  # type: ignore[override]
    ):
        if not data:
            try:
                response = cls.client.refunds.get(cls.get_payment_provider_id(payment))

            except ApiError as error:
                raise SquareException(error) from error

            data = response.refund

        if not data:
            raise PaymentException(
                f"Transaction failed to sync after refund for payment {payment.pay_object.payment_reference_id}"
            )

        cls._fill_payment_from_square_response_object(payment, data).save()


class ManualPaymentMethodMixin(abc.ABC):
    """
    Mixin for any manual payment method (one with no regiestered
    provider)
    """

    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Transaction":
        return self.create_payment_object(pay_object, value, app_fee)  # type: ignore # pylint: disable=arguments-differ

    @classmethod
    def sync_transaction(cls, *_, **__):
        return


class Cash(ManualPaymentMethodMixin, PaymentProvider):
    """Manual cash payment method"""

    description = "Manual cash payment"


class Card(ManualPaymentMethodMixin, PaymentProvider):
    """Manual card payment method"""

    description = "Manual card payment"

    @classmethod
    @classproperty
    def refund_providers(cls):
        return (ManualCardRefund(),)


class SquarePOS(PaymentProvider, SquarePaymentMethod):
    """
    Uses Square terminal api to create payment. Used for inperson card
    transactions.

    In order for this to work the following environment variables must be set:
        - SQUARE_ACCESS_TOKEN
        - SQUARE_ENVIRONMENT
    For the sandbox values please ask the webmaster. Currently all tests that
    require these values are marked with `square_integration`.and can therefor
    be skipped if not required by adding `-m "not square_integration"` to the
    test command (`make test` or `make test-v`)
    """

    description = "Square terminal card payment"

    def __init__(self, device_id: str, idempotency_key: str) -> None:
        self.device_id = device_id
        self.idempotency_key = idempotency_key
        super().__init__()

    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Transaction":
        """Send payment to point of sale device.

        Args:
            value (int): Amount of money being payed
            app_fee (int): The amount we charge for the payment.
            pay_object (Payable): The object being payed for

        Raises:
            SquareException: If the request was unsuccessful.
            PaymentException: If the payment otherwise failed

        Returns:
            Payment: Created payment
        """

        checkout = TerminalCheckoutParams(
            amount_money=MoneyParams(amount=value, currency="GBP"),
            reference_id=pay_object.payment_reference_id,
            device_options=DeviceCheckoutOptions(device_id=self.device_id),
        )

        try:
            response = self.client.terminal.checkouts.create(
                idempotency_key=self.idempotency_key, checkout=checkout
            )

        except ApiError as error:
            raise SquareException(error) from error

        if not (response.checkout and response.checkout.id):
            if response.errors:
                raise PaymentException(
                    f"Checkout failed for {pay_object.payment_reference_id} - response missing checkout or checkout ID: {response.errors[0].detail}"
                )

            raise PaymentException(
                f"Checkout failed for {pay_object.payment_reference_id} - response missing checkout or checkout ID"
            )

        square_transaction_id = response.checkout.id

        return self.create_payment_object(
            pay_object,
            value,
            app_fee,
            provider_transaction_id=square_transaction_id,
            currency="GBP",
            status=payment_models.Transaction.Status.PENDING,
        )

    @classmethod
    def list_devices(
        cls,
        product_type: Optional[Literal["TERMINAL_API"]] = None,
        status: Optional[str] = None,
        location_id: Optional[str] = None,
    ) -> list[DeviceCode]:
        """List the device codes available on square.

        Args:
            product_type (str): If provided filters the result by the
                product type. For just terminal devices use: "TERMINAL_API"
            status (str): If provided filters the result by the status type,
                for just paried devices use: "PAIRED"
            location_id (str): If provided filters the result by the
                Square location id.

        Returns:
            list of DeviceCode: A list of Devices which store the device code
                info. When connection to a device the `device_id` should be
                used.

        Raises:
            SquareException: If the square request returns an error
        """

        try:
            response = cls.client.devices.codes.list(
                product_type=product_type, status=status, location_id=location_id
            ).items

        except ApiError as error:
            raise SquareException(error) from error

        if not response:
            return []

        return response

    @classmethod
    def get_checkout(cls, checkout_id: str) -> Optional[TerminalCheckout]:
        """Get checkout info from square for a given checkout id.

        Args:
            checkout_id (str): The id of the checkout to be fetched

        Returns:
            TerminalCheckout | None: Checkout response from square

        Raises:
            SquareException: When response is not successful
        """
        try:
            response = cls.client.terminal.checkouts.get(checkout_id)

        except ApiError as error:
            raise SquareException(error) from error

        return response.checkout

    @classmethod
    def cancel(cls, payment: "payment_models.Transaction") -> None:
        """Cancel terminal checkout.

        Args:
            payment (Payment): The payment to be canceled

        Raises:
            SquareException: When request is not successful
            PaymentException: If the payment otherwise failed
        """
        if not payment.provider_transaction_id:
            raise PaymentException(
                f"Cannot cancel payment without provider_transaction_id: {payment.pay_object.payment_reference_id}"
            )

        try:
            cls.client.terminal.checkouts.cancel(payment.provider_transaction_id)

        except ApiError as error:
            raise SquareException(error) from error

    @classmethod
    def sync_transaction(
        cls, payment: "payment_models.Transaction", data: Optional[TerminalCheckout] = None  # type: ignore[override]
    ):
        """Syncs the given payment with the raw payment data"""
        payment_id = cls.get_payment_provider_id(payment)

        checkout = data if data else cls.get_checkout(payment_id)

        if not checkout:
            raise PaymentException(
                f"Transaction failed to sync due to a lack of checkout: {payment.pay_object.payment_reference_id}"
            )

        payment.provider_fee = None

        if checkout.payment_ids:
            for payment_id in checkout.payment_ids:
                payment_object = cls.get_payment(payment_id)
                if not payment_object:
                    continue

                processing_fee = cls._square_transaction_processing_fee(payment_object)
                if processing_fee:
                    payment.provider_fee = (payment.provider_fee or 0) + processing_fee

        old_status = payment.status
        payment.status = payment_models.Transaction.Status.from_square_status(
            checkout.status if checkout.status else "CANCELLED"
        )
        status_changed = not payment.status == old_status
        # If the checkout has failed
        if payment.status == payment_models.Transaction.Status.FAILED:
            # Delete the checkout payment
            if not checkout.id:
                raise PaymentException(
                    f"Transaction failed to sync due to a lack of checkout id: {payment.pay_object.payment_reference_id}"
                )
            payment_models.Transaction.objects.get(
                provider_transaction_id=checkout.id,
                provider_name=SquarePOS.name,
                status=payment_models.Transaction.Status.PENDING,
            ).delete()
            return

        payment.save()

        # If the checkout has been completed
        if (
            payment.status == payment_models.Transaction.Status.COMPLETED
            and status_changed
        ):
            payment.pay_object.complete(payment)


class SquareOnline(PaymentProvider, SquarePaymentMethod):
    """
    Uses Square checkout api to create payment. Used for online transactions.

    In order for this to work the following environment variables must be set:
        - SQUARE_ACCESS_TOKEN
        - SQUARE_ENVIRONMENT
    For the sandbox values please ask the webmaster. Currently all tests that
    require these values are marked with `square_integration`.and can therefor
    be skipped if not required by adding `-m "not square_integration"` to the
    test command (`make test` or `make test-v`)
    """

    description = "Square online card payment"

    @classmethod
    @classproperty
    def refund_providers(cls):
        return (SquareRefund(idempotency_key=str(uuid4())),)

    def __init__(
        self, nonce: str, idempotency_key: str, verify_token: Optional[str] = None
    ) -> None:
        """
        Args:
            idempotency_key (str): This value is as unique indicator of
                the payment request and is used to ensure a payment can only be
                made once. I.e. if another payment is made with the same key
                the previous payment will be returned.
            nonce (str): The nonce is a reference to the completed payment
                form on the front-end. This allows square to determine the
                payment details to use.
            verify_token(str): The verify token is used as part of 3D Secure verification, and is optional.
        """
        self.nonce = nonce
        self.idempotency_key = idempotency_key
        self.verify_token = verify_token
        super().__init__()

    def pay(
        self, value: int, app_fee: int, pay_object: "Payable"
    ) -> "payment_models.Transaction":
        """Make a payment using Square

        This makes a request to square to make a payment.

        Args:
            value (int): The value of the payment in pennies
            app_fee (int): The amount we charge for the payment.
            pay_object (Payable): The object being payed for

        Returns:
            ApiResponse: Response object from Square

        Raises:
            SquareException: If the API call was unsuccessful
            PaymentException: If the payment otherwise failed
        """

        kwargs = {
            "idempotency_key": str(self.idempotency_key),
            "source_id": self.nonce,
            "amount_money": {"amount": value, "currency": "GBP"},
            "reference_id": pay_object.payment_reference_id,
        }

        if self.verify_token:
            kwargs["verification_token"] = self.verify_token

        try:
            response = self.client.payments.create(**kwargs)

        except ApiError as error:
            raise SquareException(error) from error

        if not response.payment:
            error_message = (
                response.errors[0].detail if response.errors else "No payment returned"
            )
            raise PaymentException(
                f"Payment failed for {pay_object.payment_reference_id}: {error_message}"
            )

        card_payment_details = response.payment.card_details
        if not card_payment_details:
            error_message = (
                response.errors[0].detail
                if response.errors
                else "No card details returned"
            )
            raise PaymentException(
                f"Payment failed for {pay_object.payment_reference_id}: {error_message}"
            )

        card_details = card_payment_details.card
        amount_details = response.payment.amount_money
        square_payment_id = response.payment.id

        if not (card_details and amount_details and square_payment_id):
            error_message = (
                response.errors[0].detail
                if response.errors
                else "Incomplete payment details"
            )
            raise PaymentException(
                f"Payment failed for {pay_object.payment_reference_id}: {error_message}"
            )

        # Create payment object with info that is returned
        return self.create_payment_object(
            pay_object,
            amount_details.amount,
            app_fee,
            card_brand=card_details.card_brand,
            last_4=card_details.last4,
            provider_transaction_id=square_payment_id,
            currency=amount_details.currency,
        )

    @classmethod
    def sync_transaction(
        cls, payment: "payment_models.Transaction", data: Optional[Payment] = None  # type: ignore[override]
    ):
        """Syncs the given payment with the raw payment data"""
        payment_id = cls.get_payment_provider_id(payment)

        if data is None:
            data = cls.get_payment(payment_id)

        if not data:
            raise PaymentException(
                f"Transaction failed to sync after refund for payment {payment.pay_object.payment_reference_id}"
            )

        cls._fill_payment_from_square_response_object(payment, data).save()
