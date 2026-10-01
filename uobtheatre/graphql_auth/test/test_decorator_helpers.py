from uobtheatre.graphql_auth.test import decorators as test_decorators


def test_graphql_auth_test_decorator_helper_returns_skipif_mark():
    mark = test_decorators.skipif_django_21()
    assert mark.mark.name == "skipif"
