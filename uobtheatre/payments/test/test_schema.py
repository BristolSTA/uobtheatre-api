import pytest
from graphql_relay.node.node import to_global_id

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.payment_methods import SquarePOS
from uobtheatre.payments.test.factories import PaymentFactory


@pytest.mark.django_db
def test_payment_schema(gql_client):
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
                                                "id": to_global_id(
                                                    "PaymentNode", payment.id
                                                ),
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
                                                    "id": to_global_id(
                                                        "BookingNode",
                                                        payment.pay_object.id,
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


@pytest.mark.django_db
def test_list_devices(gql_client, mock_square):

    with mock_square(
        SquarePOS.client.devices,
        "list_device_codes",
        body={
            "device_codes": [
                {
                    "id": "X12GC60W7P7V8",
                    "name": "Boxoffice Terminal",
                    "code": "SGEKNB",
                    "device_id": "121CS145A5000029",
                    "product_type": "TERMINAL_API",
                    "location_id": "LMHP97T10P8JV",
                    "created_at": "2021-07-31T11:43:37.000Z",
                    "status": "PAIRED",
                    "status_changed_at": "2021-07-31T11:44:41.000Z",
                    "paired_at": "2021-07-31T11:44:41.000Z",
                },
                {
                    "id": "GAHYMA4WV6SVQ",
                    "name": "Terminal API Device created on 13-Aug-2021",
                    "code": "ENENKR",
                    "product_type": "TERMINAL_API",
                    "location_id": "LMHP97T10P8JV",
                    "pair_by": "2021-08-13T21:31:39.000Z",
                    "created_at": "2021-08-13T21:26:40.000Z",
                    "status": "UNPAIRED",
                    "status_changed_at": "2021-08-13T21:26:39.000Z",
                },
            ]
        },
        status_code=200,
        success=True,
    ):
        response = gql_client.execute(
            """
            query {
              squareDevices {
                id
                name
                code
                deviceId
                status
                productType
                locationId
              }
            }
            """
        )

    assert response == {
        "data": {
            "squareDevices": [
                {
                    "id": "X12GC60W7P7V8",
                    "name": "Boxoffice Terminal",
                    "code": "SGEKNB",
                    "deviceId": "121CS145A5000029",
                    "status": "PAIRED",
                    "productType": "TERMINAL_API",
                    "locationId": "LMHP97T10P8JV",
                },
                {
                    "id": "GAHYMA4WV6SVQ",
                    "name": "Terminal API Device created on 13-Aug-2021",
                    "code": "ENENKR",
                    "deviceId": None,
                    "status": "UNPAIRED",
                    "productType": "TERMINAL_API",
                    "locationId": "LMHP97T10P8JV",
                },
            ]
        }
    }
