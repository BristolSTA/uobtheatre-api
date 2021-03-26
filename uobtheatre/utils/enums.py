import graphene
from django.db import models
from graphene_django.utils.utils import get_model_fields


class EnumNode(graphene.ObjectType):
    value = graphene.String()
    description = graphene.String()


class GrapheneEnumMixin:
    """
    - Sets the type of all enums to EnumNode
    - Adds resolver for each enum field

    This results in enums being return as
    {
        value: "IN_PROGRESS"        <- Database representation (actual enum)
        description: "In progress"  <- The human readable value of the enum
    }
    """

    def _generate_enum_resolver(field_name):
        def resolver(cls, info):
            return EnumNode(
                value=getattr(cls, field_name),
                description=getattr(cls, f"get_{field_name}_display")(),
            )

        return resolver

    @classmethod
    def __init_subclass_with_meta__(cls, *args, **kwargs):
        """
        Overwrite the DjangoObjectType init to add in resolvers for every
        GrapheneImageField.
        """

        # Do the regular init
        super().__init_subclass_with_meta__(*args, **kwargs)

        # Find all the char fields which have choices
        _model_fields = get_model_fields(cls._meta.model)
        for name, field in _model_fields:
            # For every char field
            if isinstance(field, models.fields.CharField):
                # If it has choices
                choices = getattr(field, "choices", None)
                if choices:
                    # Set the field to one of our EnumNodes
                    cls._meta.fields[name] = graphene.Field(EnumNode)

        # For every EnumNode add a resolver, this resolver will return a enum
        # node with a description and value
        for name, field_type in cls._meta.fields.items():
            if hasattr(field_type, "type"):
                if field_type.type == EnumNode:
                    print(f"{name} is an EnumNode")
                    setattr(cls, f"resolve_{name}", cls._generate_enum_resolver(name))
