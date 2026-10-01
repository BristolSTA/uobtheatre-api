from unittest import mock

import graphene
from graphene import NonNull

from uobtheatre.graphql_auth.bases import (
    DynamicArgsMixin,
    DynamicInputMixin,
    MutationMixin,
    RelayMutationMixin,
)
from uobtheatre.graphql_auth.connection import CountableConnection


class _ParentMutation:
    @classmethod
    def mutate(cls, root, info, **kwargs):
        return {"called": "parent_mutate", **kwargs}


class _ChildMutation(MutationMixin, _ParentMutation):
    @classmethod
    def resolve_mutation(cls, root, info, **kwargs):
        return {"called": "resolve_mutation", **kwargs}


class _ParentRelayMutation:
    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        return {"called": "parent_payload", **kwargs}


class _ChildRelayMutation(RelayMutationMixin, _ParentRelayMutation):
    @classmethod
    def resolve_mutation(cls, root, info, **kwargs):
        return {"called": "resolve_payload", **kwargs}


class _DynamicArgsDictMutation(DynamicArgsMixin, graphene.Mutation):
    class Arguments:
        pass

    ok = graphene.Boolean()
    _args = {"nickname": "String"}
    _required_args = {"age": "Int"}

    @classmethod
    def mutate(cls, root, info, **kwargs):
        return cls(ok=True)


class _DynamicArgsListMutation(DynamicArgsMixin, graphene.Mutation):
    class Arguments:
        pass

    ok = graphene.Boolean()
    _args = ["nickname"]
    _required_args = ["age"]

    @classmethod
    def mutate(cls, root, info, **kwargs):
        return cls(ok=True)


class _DynamicInputDictMutation(DynamicInputMixin, graphene.ClientIDMutation):
    class Input:
        pass

    ok = graphene.Boolean()
    _inputs = {"nickname": "String"}
    _required_inputs = {"age": "Int"}

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        return cls(ok=True)


class _DynamicInputListMutation(DynamicInputMixin, graphene.ClientIDMutation):
    class Input:
        pass

    ok = graphene.Boolean()
    _inputs = ["nickname"]
    _required_inputs = ["age"]

    @classmethod
    def mutate_and_get_payload(cls, root, info, **kwargs):
        return cls(ok=True)


def test_mutation_mixins_delegate_to_resolvers_and_parent_methods():
    assert _ChildMutation.mutate(None, None, value=1) == {
        "called": "resolve_mutation",
        "value": 1,
    }
    assert _ChildMutation.parent_resolve(None, None, value=2) == {
        "called": "parent_mutate",
        "value": 2,
    }

    assert _ChildRelayMutation.mutate_and_get_payload(None, None, value=3) == {
        "called": "resolve_payload",
        "value": 3,
    }
    assert _ChildRelayMutation.parent_resolve(None, None, value=4) == {
        "called": "parent_payload",
        "value": 4,
    }


def test_dynamic_mixins_populate_args_and_input_fields():
    _DynamicArgsDictMutation.Field()
    _DynamicArgsListMutation.Field()

    args_dict = _DynamicArgsDictMutation._meta.arguments
    assert "nickname" in args_dict
    assert "age" in args_dict
    assert isinstance(args_dict["age"].type, NonNull)

    args_list = _DynamicArgsListMutation._meta.arguments
    assert "nickname" in args_list
    assert "age" in args_list

    _DynamicInputDictMutation.Field()
    _DynamicInputListMutation.Field()

    input_dict = _DynamicInputDictMutation._meta.arguments[
        "input"
    ]._meta.fields
    assert "nickname" in input_dict
    assert "age" in input_dict

    input_list = _DynamicInputListMutation._meta.arguments[
        "input"
    ]._meta.fields
    assert "nickname" in input_list
    assert "age" in input_list


def test_dynamic_mixins_handle_non_list_non_dict_inputs():
    class ArgsOther(DynamicArgsMixin, graphene.Mutation):
        class Arguments:
            pass

        ok = graphene.Boolean()
        _args = ("tuple",)
        _required_args = ("tuple",)

        @classmethod
        def mutate(cls, root, info, **kwargs):
            return cls(ok=True)

    class InputOther(DynamicInputMixin, graphene.ClientIDMutation):
        class Input:
            pass

        ok = graphene.Boolean()
        _inputs = ("tuple",)
        _required_inputs = ("tuple",)

        @classmethod
        def mutate_and_get_payload(cls, root, info, **kwargs):
            return cls(ok=True)

    assert ArgsOther.Field() is not None
    assert InputOther.Field() is not None


def test_connection_resolve_total_count_uses_iterable_count():
    connection = CountableConnection.__new__(CountableConnection)
    connection.iterable = mock.Mock()
    connection.iterable.count.return_value = 7

    assert connection.resolve_total_count(info=None) == 7
