FROM python:3.9
ENV PYTHONUNBUFFERED 1

# Adds our application code to the image
COPY . code
WORKDIR code

RUN pip install -r requirements.txt -r dev-requirements.txt

EXPOSE 8000

# Run the production server
CMD gunicorn config.wsgi:application --bind 0.0.0.0:8000
