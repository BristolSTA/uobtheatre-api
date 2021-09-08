export COMPOSE_FILE = local.yml

## Defines the app varaible. This reference the module which is being used
APP=$(if $(app),uobtheatre/$(app)/test,)
export APP

## Defines the test path:
## If 		the varaible test_path is secified test_path is used
## else if 	the app varaible is specified the apps test path is used
## else  	it is set to none
TEST_PATH=$(if $(path),$(path),$(if $(APP),$(APP),))
export TEST_PATH

## Defines the test varaible
## This allows the users to specify a list of tests to run
TEST=$(if $(test),-k '$(test)',)
export TEST

ifneq (,$(findstring a,  $(MAKEFLAGS)))
  VERBOSE=1
  export VERBOSE
endif

PONY: help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

up: ## Run background
	docker-compose up -d api db

up-v: ## Run verbose
	docker-compose up

up-adminer:  ## Up adminer on port 8001
	docker-compose up -d adminer

down: ## Down
	docker-compose down

dump: ## dumps databse objects into fixture
	docker-compose run --rm api python manage.py dumpdata users images addresses venues societies productions discounts bookings payments --indent 2 > db.json

migrations: ## Make the migrations
	docker-compose run --rm api python manage.py makemigrations

migrations-without-user: ## Make the migrations without setting the user (the user will probably break windows)
	docker-compose run --rm api python manage.py makemigrations

migrate: ## Do the migrations
	docker-compose run api python manage.py migrate

check-users: ## Do the migrations
	docker-compose run api `python manage.py number_of_users | tail -n 1` | grep 0

seed: ## Seed the db with some example data
	docker-compose run api python manage.py loaddata uobtheatre/images/fixtures.json uobtheatre/addresses/fixtures.json uobtheatre/users/fixtures.json uobtheatre/venues/fixtures.json uobtheatre/societies/fixtures.json uobtheatre/productions/fixtures.json uobtheatre/bookings/fixtures.json

seed-testfixtures: ## Seed the data for e2e testing
	docker-compose run api python manage.py loaddata db.json

superuser: ## Seed the db with admin superuser
	docker-compose run api python manage.py loaddata uobtheatre/users/fixtures.json

psql: ## Do the migrations
	docker-compose exec postgres psql -d postgres -U postgres

clean: ## Remove all the things
	docker-compose down --volumes --rmi all || true

test: ## Run unit tests in docker container
	docker-compose run --rm api pytest --cov uobtheatre --cov-fail-under 100 --cov-report term-missing $(TEST_PATH) $(TEST)

test-v: ## Run verbose unit tests in docker container, use test_path to specify a test file/directory, app to specify a module and test to specify specific tests to be run.
	docker-compose run --rm api coverage run -m pytest -s -vv $(TEST_PATH) $(TEST)

coverage: ## Generate test coverage report
	docker-compose run --rm api coverage run --source=uobtheatre -m pytest -m "not square_integration"
	docker-compose run --rm api coverage html
	# docker-compose run --rm api coveralls

coverage-nr: ## Generate test coverage report from last test run
	docker-compose run --rm api coverage html

black: ## Run black linter
	docker-compose run --rm api black .

isort: ## Run isort to sort imports
	docker-compose run --rm api isort .

pylint: ## Run pylint to check uobtheatre code
	docker-compose run --rm api pylint uobtheatre

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
	docker rm -f uobtheatre-postgres
	docker volume rm uobtheatre-api_uobtheatre_local_postgres_data
	docker volume rm uobtheatre-api_uobtheatre_local_postgres_data_backups
	make migrate

clean-migrations: ## Do the migrations from scratch
	make clean-app-migrations
	make clean-postgres-migrate

clean-migrations-tom: ## Do the migrations from scratch
	find . -path "*/migrations/*.py" -not -name "__init__.py" -delete
	docker-compose run --rm --user "$$(id -u):$$(id -g)" api python manage.py makemigrations
	make clean-postgres-migrate

mypy: ## Type checking - mypy
	docker-compose run --rm api mypy uobtheatre

schema: ## Dumps graphql schema in schema.json
	docker-compose run --rm api ./manage.py graphql_schema --schema uobtheatre.schema.schema --out schema.graphql

pr: ## Runs everything required (that is not included in precommit) for a pr
	make schema
	make test

build:
	docker-compose build api

django-shell: ## Open django shell
	docker-compose run --rm api python manage.py shell
