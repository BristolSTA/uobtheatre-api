import re
import requests
import uuid


performance_id = "UGVyZm9ybWFuY2VOb2RIOjlw"
seat_group_id = "U2VhdEdyb3VwTm9kZTox"
concession_type_id = "Q29uY2Vzc2lvblR5cGVOb2RlOjE1"
url = "https://staging.api.uobtheatre.com/graphql/"

def send_query(query,token = None):
    return requests.post(url, json={'query': query}, headers={"Authorization": f"JWT {token}"}).json()

login_query = """
    mutation {
        login(email: "admin@email.com", password: "strongpassword") {
            token
        }
    }
"""

user_token = send_query(login_query)["data"]["login"]["token"]

for i in range(204):
    create_query = """
        mutation {
            createBooking(performanceId: "%s", tickets: [{seatGroupId: "%s", concessionTypeId: "%s"}]) {
                success
                booking {
                    id
                    reference
                    priceBreakdown {
                        totalPrice
                    }
                }
                errors {
                    ... on NonFieldError {
                        message
                    }
                }
            }
        }
    """ % (performance_id, seat_group_id, concession_type_id)

    response = send_query(create_query, user_token)
    print(response)
    price = response["data"]["createBooking"]["booking"]["priceBreakdown"]["totalPrice"]
    id = response["data"]["createBooking"]["booking"]["id"]

    pay_query = """
        mutation {
            payBooking(bookingId: "%s", nonce: "cnon:card-nonce-ok", paymentProvider: SQUARE_ONLINE, idempotencyKey: "%s", price: %s) {
                success
            }
        }
    """ % (id, uuid.uuid4(), price)

    response = send_query(pay_query, user_token)
    if response["data"]["payBooking"]["success"]:
        print("Booking created")
