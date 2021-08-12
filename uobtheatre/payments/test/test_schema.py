import pytest

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.test.factories import PaymentFactory


@pytest.mark.django_db
def test_payment_schema(gql_client, gql_id):
    booking = BookingFactory(user=gql_client.login().user)
    payment = PaymentFactory(pay_object=booking)

    response = gql_client.execute(
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
