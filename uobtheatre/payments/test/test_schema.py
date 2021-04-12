import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.test.factories import PaymentFactroy


@pytest.mark.django_db
def test_payment_schema(gql_client_flexible, gql_id):
    booking = BookingFactory(user=gql_client_flexible.get_user())
    payment = PaymentFactroy(pay_object=booking)

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
                        type
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
                                                "type": str(payment.type),
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
