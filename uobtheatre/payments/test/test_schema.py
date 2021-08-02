import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.test.factories import PaymentFactory


@pytest.mark.django_db
def test_payment_schema(gql_client_flexible, gql_id):
    booking = BookingFactory(user=gql_client_flexible.user)
    payment = PaymentFactory(pay_object=booking)

    response = gql_client_flexible.execute(
        """
        {
          me {
            bookings {
              edges {
                node {
                  payments {
                    edges {
                      node {
                        id
                        createdAt
                        updatedAt
                        type {
                          value
                          description
                        }
                        provider {
                          value
                          description
                        }
                        providerPaymentId
                        value
                        currency
                        cardBrand
                        last4
                        url
                        payObject {
                          ... on BookingNode {
                            id
                            status {
                              value
                              description
                            }
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        }
        """
    )

    assert response == {
        "data": {
            "me": {
                "bookings": {
                    "edges": [
                        {
                            "node": {
                                "payments": {
                                    "edges": [
                                        {
                                            "node": {
                                                "id": gql_id(payment.id, "PaymentNode"),
                                                "createdAt": payment.created_at.isoformat(),
                                                "updatedAt": payment.updated_at.isoformat(),
                                                "type": {
                                                    "value": str(payment.type).upper(),
                                                    "description": payment.get_type_display(),
                                                },
                                                "provider": {
                                                    "value": str(
                                                        payment.provider
                                                    ).upper(),
                                                    "description": payment.get_provider_display(),
                                                },
                                                "providerPaymentId": payment.provider_payment_id,
                                                "value": payment.value,
                                                "currency": payment.currency,
                                                "cardBrand": payment.card_brand,
                                                "last4": payment.last_4,
                                                "url": payment.url(),
                                                "payObject": {
                                                    "id": gql_id(
                                                        payment.pay_object.id,
                                                        "BookingNode",
                                                    ),
                                                    "status": {
                                                        "value": str(
                                                            payment.pay_object.status
                                                        ),
                                                        "description": payment.pay_object.get_status_display(),
                                                    },
                                                },
                                            }
                                        }
                                    ]
                                }
                            }
                        },
                    ]
                }
            }
        }
    }


def test_square_webhook_terminal_checkout_updated():
    body = {
        "merchant_id": "ML8M1AQ1GQG2K",
        "type": "terminal.checkout.updated",
        "event_id": "f958651d-def0-4ef6-bb75-3d82c3bdf9e7",
        "created_at": "2021-08-01T09:36:44.547787606Z",
        "data": {
            "type": "checkout.event",
            "id": "dhgENdnFOPXqO",
            "object": {
                "checkout": {
                    "amount_money": {"amount": 111, "currency": "USD"},
                    "app_id": "sq0idp-734Md5EcFjFmwpaR0Snm6g",
                    "created_at": "2020-04-10T14:43:55.262Z",
                    "deadline_duration": "PT5M",
                    "device_options": {
                        "device_id": "907CS13101300122",
                        "skip_receipt_screen": False,
                        "tip_settings": {"allow_tipping": False},
                    },
                    "id": "dhgENdnFOPXqO",
                    "note": "A simple note",
                    "payment_ids": ["dgzrZTeIeVuOGwYgekoTHsPouaB"],
                    "reference_id": "id72709",
                    "status": "COMPLETED",
                    "updated_at": "2020-04-10T14:44:06.039Z",
                }
            },
        },
    }
