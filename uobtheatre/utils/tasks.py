from typing import TYPE_CHECKING

from uobtheatre.celery import app

if TYPE_CHECKING:
    pass

# Tasks


@app.task
def refund_booking(booking_pk: int, user_pk: int):
    from uobtheatre.bookings.models import Booking
    from uobtheatre.users.models import User

    booking = Booking.objects.get(pk=booking_pk)
    user = User.objects.get(pk=user_pk)

    booking.refund(user, send_admin_email=False)
