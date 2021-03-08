FROM python:3.8
ENV PYTHONUNBUFFERED 1

# Adds our application code to the image
COPY . code
WORKDIR code

RUN pip install -r requirements.txt -r dev-requirements.txt

EXPOSE 8000

# Run the production server
CMD newrelic-admin run-program gunicorn --bind 0.0.0.0:$PORT --access-logfile - uobtheatre-api.wsgi:application
