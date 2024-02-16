# uobtheatre-api

![Gitub actions](https://github.com/BristolSTA/uobtheatre-api/workflows/Python%20package/badge.svg?branch=main)
[![Coverage Status](https://coveralls.io/repos/github/BristolSTA/uobtheatre-api/badge.svg?branch=main)](https://coveralls.io/github/BristolSTA/uobtheatre-api?branch=main)

# Quick Start (Getting the api running)

If you have docker and docker-compose installed run:

```
make setup
```

This will:

- Pull all the docker images
- Build the api image
- Collect the static files
- Setup a venv
- Start the api and db

(If you are on windows you will need to copy the commands into git bash from the makefile or use wsl)

# Prerequisites (Local dev)

- Python 3.10
- [docker](https://docs.docker.com/get-docker/)
- [docker-compose](https://docs.docker.com/compose/install/)


## Visual Studio Dev Container

This repository has support for users of VS Code. If you use VS Code and have Docker and the "Remote Containers" extension installed, you can get started in under 5 minutes:
* Clone this repository somewhere on your computer (If using WSL, this should be inside your WSL environment)
* Either: a) open the folder through VS Code or b) navgiate to the folder in a CLI and type `code .`
* If you have the correct extensions installed, you will see a popup on the bottom right asking if you would like to open in a remote container. Click this, and sit back!

# Local Development :computer:

Everything you need should be contained in a docker container. For now all the commands you need are in a make file.

To start the dev server for local development:

```bash
make up
```

If you would like to set some environment variables, you can copy the `.env.example` in the root of the project to `.env`.

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
make test path=uobtheatre/bookings/test/test_views.py
```

and to run a single test

```
make test path=uobtheatre/bookings/test/test_views.py test=test_name
```

## Seeding

There are a load of fixtures save in fixture.json in all the moduels. These can be loaded into the database with `make seed`.
Most notably this will add an admin users called with the following details:

email: admin@email.com
password: strongpassword

## Packages :package:

When adding a package follow these steps:

1. Add the pacakge to the correct requirements file:
- base - Is for any package required in both local and production environments
- local - Is for any package required in only local environments
- production - Is for any package required in only production environments

The API image will then need rebuilding to add this dependency. Run:

```
make build
```

This does the following:
- Set the requirements for mypy
- Rebuild the api

If mypy gives an error about not being able to find the new package, add it to the list of "additional_dependencies" in `.pre-commit-config.yaml`.
