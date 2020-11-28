PONY: help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

up: ## Run api
	docker-compose up -d

up-v: ## Run api with logs
	docker-compose up

down: ## Bring down api
	docker-compose down

superuser: ## Create a superuser in django
	docker-compose run api python manage.py createsuperuser 

admin-superuser: ## Create a superuser in django
	docker-compose run api python manage.py createsuperusernoargs --username admin2 --password admin --noinput --email 'blank@email.com'

migrations: ## Make the migrations
	docker-compose run --rm api python manage.py makemigrations

migrate: ## Do the migrations
	docker-compose run api python manage.py migrate

seed: ## Seed the db with some example data 
	docker-compose run api python manage.py loaddata uobtheatre/users/fixtures.json uobtheatre/venues/fixtures.json uobtheatre/societies/fixtures.json uobtheatre/productions/fixtures.json uobtheatre/bookings/fixtures.json
	make admin-superuser

psql: ## Do the migrations
	docker-compose exec postgres psql -d postgres -U postgres 

clean: ## Remove all the things
	docker-compose down --volumes --rmi all || true

test: ## Run unit tests in docker container 
	docker-compose run --rm api coverage run -m pytest

test-v: ## Run verbose unit tests in docker container 
	docker-compose run --rm api coverage run -m pytest -s -vv

coverage: ## Generate test coverage report 
	docker-compose run --rm api coverage html

black: ## Run verbose unit tests in docker container 
	docker-compose run --rm api black .

isort: ## Run verbose unit tests in docker container 
	docker-compose run --rm api isort .

setup-pipenv: ## Setup pipenv locally
	pipenv --python 3.8
	# If black is causing issues: pipenv install --dev --pre
	pipenv install

pipenv-install: ## Setup pipenv locally
	docker-compose run --rm api cd /tmp; pipenv lock --requirements > requirements.txt; pip install -r /tmp/requirements.txt

clean-app-migrations: ## Generate clean migrations for productions
	find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
	make migrations

clean-postgres-migrate: ## Apply clean migrations to postgres
	docker rm -f uobtheatre-api_postgres_1
	docker volume rm uobtheatre-api_postgres_data
	make migrate 

clean-migrations: ## Do the migrations from scratch
	make clean-app-migrations
	make clean-postgres-migrate
