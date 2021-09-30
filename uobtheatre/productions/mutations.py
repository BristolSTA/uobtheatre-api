import graphene

from uobtheatre.productions.models import AudienceWarning, Performance, Production
from uobtheatre.societies.models import Society
from uobtheatre.utils.schema import IdInputField, SafeMutation


class AudienceWarningInput(graphene.InputObjectType):
    description = graphene.String()


class PerformanceInput(graphene.InputObjectType):
    venue = IdInputField()
    doors_open = graphene.DateTime()
    start = graphene.DateTime()
    end = graphene.DateTime()
    description = graphene.String()
    extra_information = graphene.String()
    capacity = graphene.Int()

    # TODO
    # seat_groups =


class CreateProduction(SafeMutation):
    production = graphene.Field("uobtheatre.productions.schema.ProductionNode")

    class Arguments:
        name = graphene.String(required=True)
        subtitle = graphene.String()
        society_id = IdInputField()
        age_rating = graphene.Int()
        facebook_event = graphene.String()
        warnings = graphene.List(AudienceWarningInput)
        performances = graphene.List(PerformanceInput)

    @classmethod
    def resolve_mutation(
        cls,
        _,
        info,
        name,
        warnings=None,
        performances=None,
        society_id=None,
        **kwargs,
    ):
        society = Society.objects.get(id=society_id)
        production = Production.objects.create(name=name, society=society, **kwargs)

        if warnings:
            production_warnings = [
                AudienceWarning.objects.get_or_create(description=warning.description)[
                    0
                ]
                for warning in warnings
            ]
            production.warnings.add(*production_warnings)

        if performances:
            for performance in performances:
                Performance.objects.create(
                    production=production, **performance.__dict__
                )

        return CreateProduction(production=production)


class Mutation(graphene.ObjectType):
    create_production = CreateProduction.Field()
