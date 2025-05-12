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

## By default, ignore the "visualisation" tests for the mail, as these are "pseudo-tests" used when updating the mail templates
TEST+= --ignore=uobtheatre/mail/visualisations/
export TEST

ifneq (,$(findstring a,  $(MAKEFLAGS)))
  VERBOSE=1
  export VERBOSE
endif

COMMAND_PREFIX=$(if $(DEV_CONTAINER),,docker compose run --rm api)

PONY: help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

setup:
	docker compose pull
	make build
	make collect-static
	python -m venv .venv
	source .venv/bin/activate
	make up

setup-devcontainer:
	pip install -r requirements/base.txt
	pip install -r requirements/local.txt
	make migrate

up: ## Run background
	docker compose up -d api postgres celery celery-beat redis

up-v: ## Run verbose
	docker compose up

up-adminer:  ## Up adminer on port 8001
	docker compose up -d adminer

down: ## Down
	docker compose down

dump: ## dumps databse objects into fixture
	$(COMMAND_PREFIX) python manage.py dumpdata users images addresses venues societies productions discounts bookings payments --indent 2 > db.json

migrations: ## Make the migrations
	$(COMMAND_PREFIX) python manage.py makemigrations

migrations-without-user: ## Make the migrations without setting the user (the user will probably break windows)
	$(COMMAND_PREFIX) python manage.py makemigrations

merge-migrations: ## Merge conflicting migrations
	$(COMMAND_PREFIX) python manage.py makemigrations --merge

migrate: ## Do the migrations
	$(COMMAND_PREFIX) python manage.py migrate

collect-static:
	$(COMMAND_PREFIX) python manage.py collectstatic

check-users: ## Do the migrations
	$(COMMAND_PREFIX) `python manage.py number_of_users | tail -n 1` | grep 0

seed: ## Seed the db with some example data
	$(COMMAND_PREFIX) python manage.py loaddata uobtheatre/images/fixtures.json uobtheatre/addresses/fixtures.json uobtheatre/users/fixtures.json uobtheatre/venues/fixtures.json uobtheatre/societies/fixtures.json uobtheatre/productions/fixtures.json uobtheatre/bookings/fixtures.json uobtheatre/site_messages/fixtures.json

seed-testfixtures: ## Seed the data for e2e testing
	$(COMMAND_PREFIX) python manage.py loaddata db.json

superuser: ## Seed the db with admin superuser
	$(COMMAND_PREFIX) python manage.py loaddata uobtheatre/users/fixtures.json

psql: ## Connect to db
	docker compose exec postgres psql -d postgres -U postgres

clean: ## Remove all the things
	docker compose down --volumes --rmi all || true

test: ## Run unit tests in docker container
	$(COMMAND_PREFIX) pytest -k "not system_test" --cov uobtheatre --cov-fail-under 100 --cov-report term-missing $(TEST_PATH) $(TEST)

test-v: ## Run verbose unit tests in docker container, use test_path to specify a test file/directory, app to specify a module and test to specify specific tests to be run.
	$(COMMAND_PREFIX) coverage run -m pytest -k "not system_test" -s -vv $(TEST_PATH) $(TEST)

test-system: ## Run system tests in docker container
	$(COMMAND_PREFIX) pytest --cov uobtheatre -m "system_test"

coverage: ## Generate test coverage report
	$(COMMAND_PREFIX) coverage run --source=uobtheatre -m pytest -m "not square_integration"
	$(COMMAND_PREFIX) coverage html
	# $(COMMAND_PREFIX) coveralls

coverage-nr: ## Generate test coverage report from last test run
	$(COMMAND_PREFIX) coverage html

black: ## Run black linter
	$(COMMAND_PREFIX) black .

isort: ## Run isort to sort imports
	$(COMMAND_PREFIX) isort .

pylint: ## Run pylint to check uobtheatre code
	$(COMMAND_PREFIX) pylint uobtheatre

lint:
	make isort
	make black
	make pylint
	make mypy

pipenv-install: ## Setup pipenv locally
	$(COMMAND_PREFIX) cd /tmp; pipenv lock --requirements > requirements.txt; pip install -r /tmp/requirements.txt

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
	docker compose run --rm --user "$$(id -u):$$(id -g)" api python manage.py makemigrations
	make clean-postgres-migrate

mypy: ## Type checking - mypy
	$(COMMAND_PREFIX) mypy uobtheatre

schema: ## Dumps graphql schema in schema.json
	$(COMMAND_PREFIX) ./manage.py graphql_schema --schema uobtheatre.schema.schema --out schema.graphql

pr: ## Runs everything required for a pr
	make schema
	make lint
	make test

build:
	docker compose build api celery

django-shell: ## Open django shell
	$(COMMAND_PREFIX) python manage.py shell

api-shell: ## Open django shell
	docker compose exec api /bin/bash

flush:
	$(COMMAND_PREFIX) python manage.py flush

## First we have to copy our static files to ensure CSS changes are carried through. Then, we can remake our HTML files for testing.
mail-vis: ## Generate HTML emails from the django templates, leveraging pytest
	$(COMMAND_PREFIX) python manage.py collectstatic --noinput && pytest uobtheatre/mail/visualisations/

## A verbose version of the above command
mail-vis-v: ## Generate HTML emails from the django templates, leveraging pytest
	$(COMMAND_PREFIX) python manage.py collectstatic --noinput && pytest -s uobtheatre/mail/visualisations/
