# Create apps

In order to create a new app

1. Create a new folder in the `uobtheare` directory and add an __init__.py inside
2. Add the apps files
3. Add the app in config/settings/common.py `INSTALLED_APPS`
4. `docker compose run --rm api python manage.py makemigrations <app_name>`
