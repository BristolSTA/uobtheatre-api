release: python manage.py migrate; python manage.py loaddata uobtheatre/addresses/fixtures.json uobtheatre/users/fixtures.json uobtheatre/venues/fixtures.json uobtheatre/societies/fixtures.json uobtheatre/productions/fixtures.json uobtheatre/bookings/fixtures.json
web: gunicorn config.wsgi --preload --log-file -
