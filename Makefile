PONY: help

help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'

up: ## Run api
	docker-compose up -d

down: ## Bring down api
	docker-compose down

superuser: ## Create a superuser in django
	docker-compose run api python manage.py createsuperuser 

migrations: ## Make the migrations
	docker-compose run --rm api python manage.py makemigrations

migrate: ## Do the migrations
	docker-compose run api python manage.py migrate

psql: ## Do the migrations
	docker-compose exec postgres psql -d postgres -U postgres 

clean: ## Remove all the things
	docker-compose down --volumes --rmi all || true

test: ## Run unit tests in docker container 
	docker-compose run --rm api coverage run -m pytest

test-v: ## Run verbose unit tests in docker container 
	docker-compose run --rm api coverage run -m pytest -vv
