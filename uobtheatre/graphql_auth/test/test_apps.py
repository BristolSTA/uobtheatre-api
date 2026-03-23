from importlib import import_module

from uobtheatre.graphql_auth.apps import GraphQLAuthConfig


def test_graphql_auth_config_metadata():
    assert GraphQLAuthConfig.name == "uobtheatre.graphql_auth"
    assert GraphQLAuthConfig.verbose_name == "GraphQL Auth"


def test_graphql_auth_config_ready_imports_signals(monkeypatch):
    monkeypatch.delitem(
        __import__("sys").modules,
        "uobtheatre.graphql_auth.signals",
        raising=False,
    )

    config = GraphQLAuthConfig(
        "uobtheatre.graphql_auth", import_module("uobtheatre.graphql_auth")
    )
    # ready() should import signals and complete without error.
    assert config.ready() is None
