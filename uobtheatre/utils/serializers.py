from rest_framework import relations, serializers


class UserIdSerializer(serializers.UUIDField):
    def __init__(self, source="user.id"):
        super().__init__(format="hex_verbose", source=source)


# Add _id to releated fields
# https://stackoverflow.com/a/37908893
class IdManyRelatedField(relations.ManyRelatedField):
    field_name_suffix = "_ids"

    def bind(self, field_name, parent):
        self.source = field_name[: -len(self.field_name_suffix)]
        super(IdManyRelatedField, self).bind(field_name, parent)


class IdPrimaryKeyRelatedField(relations.PrimaryKeyRelatedField):
    """
    Field that  the field name to FIELD_NAME_id.
    Only works together the our ModelSerializer.
    """

    many_related_field_class = IdManyRelatedField
    field_name_suffix = "_id"

    def bind(self, field_name, parent):
        """
        Called when the field is bound to the serializer.
        Changes the source  so that the original field name is used (removes
        the _id suffix).
        """
        if field_name:
            self.source = field_name[: -len(self.field_name_suffix)]
        super(IdPrimaryKeyRelatedField, self).bind(field_name, parent)


class AppendIdSerializerMixin(object):
    """
    Append '_id' to FK field names
    https://gist.github.com/ostcar/eb78515a41ab41d1755b
    """

    serializer_related_field = IdPrimaryKeyRelatedField

    def get_fields(self):
        fields = super(AppendIdSerializerMixin, self).get_fields()
        new_fields = type(fields)()
        for field_name, field in fields.items():
            if getattr(field, "field_name_suffix", None):
                field_name += field.field_name_suffix
            new_fields[field_name] = field
        return new_fields
