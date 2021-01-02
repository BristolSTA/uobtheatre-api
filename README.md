#uobtheatre-api

![Gitub actions](https://github.com/BristolSTA/uobtheatre-api/workflows/Python%20package/badge.svg?branch=main)

API for uobtheatre. Check out the project's [documentation](http://BristolSTA.github.io/uobtheatre-api/).

# Prerequisites

- [Docker](https://docs.docker.com/get-docker/)

# Local Development

Everything you need should be contained in a docker container. For now all the commands you need are in a make file.

To start the dev server for local development:

```bash
make up
```

## Pre-commit

Pre commit runs everything required before a pr can be merged. To install run

`pip install pre-commit`
