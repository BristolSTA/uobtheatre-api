# uobtheatre-api

![Gitub actions](https://github.com/BristolSTA/uobtheatre-api/workflows/Python%20package/badge.svg?branch=main)
[![Coverage Status](https://coveralls.io/repos/github/BristolSTA/uobtheatre-api/badge.svg?branch=main)](https://coveralls.io/github/BristolSTA/uobtheatre-api?branch=main)

API for uobtheatre. Check out the project's [documentation](http://BristolSTA.github.io/uobtheatre-api/).

# Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Pipenv](https://pypi.org/project/pipenv/)

Create a pipenv environment and use it

```
pipenv --python 3.8
pipenv install --dev
pipenv shell
```

If you need to use a python thing locally (not in docker) go into pipenv with `pipenv shell`.

## Pre-commit

Pre-commit runs everything required before a pr can be merged.

## Install in pipenv
It should already be installed for you in pipenv so just make sure you are in pipenv
shell (`pipenv shell`) before running `git commit`.

Then run `pre-commit install`

## Install locally
If you don't want to live inside a pipenv shell then just install pre-commit
locally `pip install pre-commit` (or `python3 -m pip install pre-commit`).

Then run `pre-commit install`

## Visual studio dev container
TODO if people care

# Local Development :computer:

Everything you need should be contained in a docker container. For now all the commands you need are in a make file.

To start the dev server for local development:

```bash
make up
```

## Migrations :twisted_rightwards_arrows:

A migration explains how a database changes between releases. It contains sql
command (or equalivalent) to update an existing database to the required schema
for the new version of the api. For example if you add a `name` field to the
user object this will need to be reflected in the db before the new version of
the api can work.

Django generates migrations for with the `make migrations` command. These
migrations can then be applied to the running postgres instance with `make
migrate`. Every time you generate a new set of migrations it will create a new
file with the changes. For now always use `make clean-migrations` to remove all
the migrations before generating the new set. This prevents us from having lots
of files with small migration changes. This is good for now but will have to
stop when we start deploying a version of the api.

After starting work on a new branch your running postgres container might be
different to the schema expected on the branch. To fix this run `make
clean-postgres-migrations`. This removes your current postgres container and
applies the migrations already in the branch (without generating new ones).

## Testing :mag:

To run the tests

```
make test
```

This will run the full test suit. It will be required that these pass and have
sufficient coverage for a pr to be merged.

To run testing with verbose output

```
make test-v
```

and to run a single test file run

```
docker-compose run --rm api pytest --cov uobtheatre -vv -s uobtheatre/bookings/test/test_views.py
```

and to run a single test

```
docker-compose run --rm api pytest --cov uobtheatre -vv -s uobtheatre/bookings/test/test_views.py -k 'test_name'
```

## Packages :package:

When adding a package run 

`pipenv install package-name`

This will add the package to the pipenv environemnt. However it will not update the docker image. This means you will need to remove the current image with `make clean` and rebuild with `make up`.

This also means when starting work on a new branch which has a new package you will also need to clean and rebuild. 
