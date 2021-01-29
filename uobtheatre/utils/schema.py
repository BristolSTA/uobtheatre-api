import graphene
from graphql_relay.node.node import from_global_id


class GrapheneImageField(graphene.Field):
    pass


class GrapheneImageFieldNode(graphene.ObjectType):
    url = graphene.String()
    name = graphene.String()


def generate_resolver(field_name):
    def resolver(self, info):
        if not getattr(self, field_name) or not hasattr(
            getattr(self, field_name), "url"
        ):
            return None
        return getattr(self, field_name)

    return resolver


class GrapheneImageMixin:
    """
    Adds image support to graphene.Field
    """

    @classmethod
    def __init_subclass_with_meta__(self, *args, **kwargs):
        """
        Overwrite the DjangoObjectType init to add in resolvers for every
        GrapheneImageField.
        """

        # Do the regular init
        super().__init_subclass_with_meta__(*args, **kwargs)

        # For every GrapheneImageField add a resolver
        for name, type in self._meta.fields.items():
            if isinstance(type, GrapheneImageField):
                setattr(self, f"resolve_{name}", generate_resolver(name))


def _covert_id_field_to_object(item):
    new_item = item.copy()
    if isinstance(item, dict):
        for key, value in item.items():
            if key.endswith("_id") and isinstance(value, str):
                new_item[key[:-3] + "_local_id"] = from_global_id(value)[1]
            else:
                new_item[key] = _covert_id_field_to_object(value)
        return new_item
    if isinstance(item, list):
        return [_covert_id_field_to_object(x) for x in item]
    return item


class RelayIdMutationMixin:
    @classmethod
    def mutate(cls, root, info, input):
        print("hlloe")
        for key, value in input.items():
            print(f"{key}: {value}")
        for key, value in _covert_id_field_to_object(input).items():
            print(f"{key}: {value}")
        return super().mutate(root, info, _covert_id_field_to_object(input))
