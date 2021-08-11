from typing import Any, Callable

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

    This results in enums being returned as
    {
        value: "IN_PROGRESS"        <- Database representation (actual enum)
        description: "In progress"  <- The human readable value of the enum
    }
    """

    @classmethod
    def _generate_enum_resolver(cls, field_name: str) -> Callable[[Any, Any], EnumNode]:
        """Create a resolver for the enum.

        For every enum a resolver is created which returns an EnumNode
        containing the enums value as well as its display name.

        Args:
            field_name (str): The name of the field which is an enum

        Returns:
            EnumNode: An enum node containing, value (the enum) and description
                (human readable display name of the enum).
        """

        def resolver(self, info) -> EnumNode:
            """Resolver for enum values

            Returns:
                EnumNode: The enum node for the field given to
                    _generate_enum_resolver
            """
            return EnumNode(
                value=getattr(self, field_name).upper(),
                description=(
                    # I think pylint does not understand use of walrus in
                    # ternary if statement
                    desc_getter()  # pylint: disable=used-before-assignment
                    if (desc_getter := getattr(self, f"get_{field_name}_display", None))
                    else None
                ),
            )

        return resolver

    @classmethod
    def __init_subclass_with_meta__(cls, *args, **kwargs):
        """
        Overwrite the DjangoObjectType init to add in resolvers for every
        EnumNode.
        """
        # Do the regular init
        super().__init_subclass_with_meta__(*args, **kwargs)

        # Find all the char fields which have choices
        _model_fields = get_model_fields(cls._meta.model)

        for name, field in _model_fields:
            # For every char field that doesnt have a custom resolver already
            if isinstance(field, models.fields.CharField) and not hasattr(
                cls, f"resolve_{name}"
            ):
                # If it has choices
                choices = getattr(field, "choices", None)
                if choices:
                    # Set the field to one of our EnumNodes
                    cls._meta.fields[name] = graphene.Field(EnumNode)

        # For every EnumNode add a resolver, this resolver will return a enum
        # node with a description and value
        for name, field_type in cls._meta.fields.items():
            # This doesnt work with certain imports, I think we might find out
            # about the true pain of this in the future.
            if (
                type(field_type)  # pylint: disable=unidiomatic-typecheck
                is graphene.types.field.Field
                and hasattr(field_type, "type")
                and field_type.type == EnumNode
                and not hasattr(cls, f"resolve_{name}")
            ):
                setattr(cls, f"resolve_{name}", cls._generate_enum_resolver(name))
