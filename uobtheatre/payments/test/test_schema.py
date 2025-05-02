import pytest
from graphql_relay.node.node import to_global_id
from guardian.shortcuts import assign_perm
from square.core.pagination import SyncPager
from square.types.device_code import DeviceCode

from uobtheatre.bookings.test.factories import BookingFactory
from uobtheatre.payments.test.factories import TransactionFactory
from uobtheatre.payments.transaction_providers import SquarePOS
from uobtheatre.productions.test.factories import PerformanceFactory


@pytest.mark.django_db
def test_payment_schema(gql_client):
    booking = BookingFactory(user=gql_client.login().user)
    payment = TransactionFactory(pay_object=booking)

    response = gql_client.execute(
        """
        {
          me {
            bookings {
              edges {
                node {
                  transactions {
                    edges {
                      node {
                        id
                        createdAt
                        updatedAt
                        type
                        providerName
                        providerTransactionId
                        value
                        currency
                        cardBrand
                        last4
                        url
                        payObject {
                          ... on BookingNode {
                            id
                            status
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
                                "transactions": {
                                    "edges": [
                                        {
                                            "node": {
                                                "id": to_global_id(
                                                    "TransactionNode", payment.id
                                                ),
                                                "createdAt": payment.created_at.isoformat(),
                                                "updatedAt": payment.updated_at.isoformat(),
                                                "type": str(payment.type).upper(),
                                                "providerName": str(
                                                    payment.provider_name
                                                ).upper(),
                                                "providerTransactionId": payment.provider_transaction_id,
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
                                                    "status": str(
                                                        payment.pay_object.status
                                                    ).upper(),
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
    PerformanceFactory()
    gql_client.login()
    assign_perm("productions.boxoffice", gql_client.user)

    mock_response = SyncPager(
        has_next=False,
        items=[
            DeviceCode(
                id="X12GC60W7P7V8",
                name="Boxoffice Terminal",
                code="SGEKNB",
                device_id="121CS145A5000029",
                product_type="TERMINAL_API",
                location_id="LMHP97T10P8JV",
                created_at="2021-07-31T11:43:37.000Z",
                status="PAIRED",
                status_changed_at="2021-07-31T11:44:41.000Z",
                paired_at="2021-07-31T11:44:41.000Z",
            ),
            DeviceCode(
                id="GAHYMA4WV6SVQ",
                name="Terminal API Device created on 13-Aug-2021",
                code="ENENKR",
                product_type="TERMINAL_API",
                location_id="LMHP97T10P8JV",
                pair_by="2021-08-13T21:31:39.000Z",
                created_at="2021-08-13T21:26:40.000Z",
                status="UNPAIRED",
                status_changed_at="2021-08-13T21:26:39.000Z",
            ),
        ],
        get_next=None,
    )

    with mock_square(SquarePOS.client.devices.codes, "list", mock_response):
        response = gql_client.execute(
            """
            query {
              paymentDevices {
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
            "paymentDevices": [
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


@pytest.mark.django_db
def test_list_devices_without_boxoffice_permissions(gql_client, mock_square):
    """
    Test that an error is returned if a user tried to list devices without
    permissions to access the boxoffice.
    """

    mock_response = SyncPager(
        has_next=False,
        items=[
            DeviceCode(
                id="X12GC60W7P7V8",
                name="Boxoffice Terminal",
                code="SGEKNB",
                device_id="121CS145A5000029",
                product_type="TERMINAL_API",
                location_id="LMHP97T10P8JV",
                created_at="2021-07-31T11:43:37.000Z",
                status="PAIRED",
                status_changed_at="2021-07-31T11:44:41.000Z",
                paired_at="2021-07-31T11:44:41.000Z",
            ),
        ],
        get_next=None,
    )

    with mock_square(SquarePOS.client.devices.codes, "list", mock_response):
        response = gql_client.execute(
            """
            query {
              paymentDevices {
                id
              }
            }
            """
        )

    assert response == {
        "data": {
            "paymentDevices": None,
        }
    }


@pytest.mark.django_db
def test_list_devices_empty_response(gql_client, mock_square):
    PerformanceFactory()
    gql_client.login()
    assign_perm("productions.boxoffice", gql_client.user)

    mock_response = SyncPager(
        has_next=False,
        items=[],
        get_next=None,
    )

    with mock_square(SquarePOS.client.devices.codes, "list", mock_response):
        response = gql_client.execute(
            """
            query {
              paymentDevices {
                id
              }
            }
            """
        )

    assert response == {"data": {"paymentDevices": []}}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "filters, expect_called, expected_args",
    [
        (
            "paymentProvider: SQUARE_POS, paired: false",
            True,
            {"product_type": "TERMINAL_API", "status": "UNPAIRED", "location_id": None},
        ),
        ("paymentProvider: SQUARE_ONLINE", False, {}),
        (
            "paymentProvider: SQUARE_POS",
            True,
            {"product_type": "TERMINAL_API", "status": None, "location_id": None},
        ),
        (
            "paymentProvider: SQUARE_POS, paired: true",
            True,
            {"product_type": "TERMINAL_API", "status": "PAIRED", "location_id": None},
        ),
    ],
)
def test_filter_list_devices(
    gql_client, mock_square, filters, expect_called, expected_args
):
    PerformanceFactory()
    gql_client.login()
    assign_perm("productions.boxoffice", gql_client.user)

    mock_response = SyncPager(
        has_next=False,
        items=[],
        get_next=None,
    )

    with mock_square(
        SquarePOS.client.devices.codes, "list", mock_response
    ) as list_devices_mock:
        response = gql_client.execute(
            """
            query {
              paymentDevices%s {
                id
              }
            }
            """
            % f"({filters})"
            if filters
            else ""
        )

    assert response == {"data": {"paymentDevices": []}}

    if expect_called:
        list_devices_mock.assert_called_once_with(**expected_args)
    else:
        list_devices_mock.assert_not_called()
