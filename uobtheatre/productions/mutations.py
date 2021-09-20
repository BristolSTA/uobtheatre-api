import graphene

from uobtheatre.productions.models import (
    AudienceWarning,
    CastMember,
    CrewMember,
    CrewRole,
    Image,
    Performance,
    PerformanceSeatGroup,
    Production,
    ProductionTeamMember,
    SeatGroup,
)
from uobtheatre.societies.models import Society
from uobtheatre.utils.schema import IdInputField, SafeMutation
from uobtheatre.venues.models import Venue


class AudienceWarningInput(graphene.InputObjectType):
    description = graphene.String()


class CastMemeberInput(graphene.InputObjectType):
    name = graphene.String()
    role = graphene.String()

    # TODO
    # profile_picture =

    def to_obj(self, production=None) -> CastMember:
        return CastMember(production=production, **self.__dict__)


class ProductionTeamMemberInput(graphene.InputObjectType):
    name = graphene.String()
    role = graphene.String()

    def to_obj(self, production=None) -> ProductionTeamMember:
        return ProductionTeamMember(production=production, **self.__dict__)


class CrewRoleInput(graphene.InputObjectType):
    name = graphene.String()
    department = graphene.Field(graphene.Enum.from_enum(CrewRole.Department))

    def to_obj(self) -> CrewRole:
        return CrewRole(**self.__dict__)


class CrewMemberInput(graphene.InputObjectType):
    name = graphene.String()
    role = graphene.Field(CrewRoleInput)

    def to_obj(self, production=None) -> CrewMember:
        role = self.role.to_obj()
        role.save()
        return CrewMember(name=self.name, role=role, production=production)


class PerformanceSeatGroupInput(graphene.InputObjectType):
    seat_group = IdInputField(required=True)
    price = graphene.Int(required=True)
    capacity = graphene.Int()

    def to_obj(self, performance=None) -> PerformanceSeatGroup:
        seat_group = SeatGroup.objects.get(id=self.seat_group)
        return PerformanceSeatGroup(
            performance=performance,
            seat_group=seat_group,
            price=self.price,
            capacity=self.capacity,
        )


class PerformanceInput(graphene.InputObjectType):
    venue_id = IdInputField()
    doors_open = graphene.DateTime()
    start = graphene.DateTime()
    end = graphene.DateTime()
    description = graphene.String()
    extra_information = graphene.String()
    capacity = graphene.Int()
    ticket_options = graphene.List(PerformanceSeatGroupInput)

    def create(self, production=None):
        performance = Performance.objects.create(
            production=production,
            venue=Venue.objects.get(id=self.venue_id) if self.venue_id else None,
            doors_open=self.doors_open,
            start=self.start,
            end=self.end,
            description=self.description,
            extra_information=self.extra_information,
            capacity=self.capacity,
        )
        PerformanceSeatGroup.objects.bulk_create(
            [
                option.to_obj(performance=performance)
                for option in self.ticket_options or []
            ]
        )


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

        crew = graphene.List(CrewMemberInput)
        production_team = graphene.List(ProductionTeamMemberInput)
        cast = graphene.List(CastMemeberInput)

        cover_image_id = IdInputField()
        poster_image_id = IdInputField()
        featured_image_id = IdInputField()

    @classmethod
    def resolve_mutation(
        cls,
        _,
        info,
        name,
        warnings=None,
        performances=None,
        society_id=None,
        cover_image_id=None,
        poster_image_id=None,
        featured_image_id=None,
        cast=None,
        crew=None,
        production_team=None,
        **kwargs,
    ):
        production = Production.objects.create(
            name=name,
            society=Society.objects.get(id=society_id) if society_id else None,
            cover_image=Image.objects.get(id=cover_image_id)
            if cover_image_id
            else None,
            poster_image=Image.objects.get(id=poster_image_id)
            if poster_image_id
            else None,
            featured_image=Image.objects.get(id=featured_image_id)
            if featured_image_id
            else None,
            **kwargs,
        )

        production.warnings.add(
            *[
                AudienceWarning.objects.get_or_create(description=warning.description)[
                    0
                ]
                for warning in warnings
            ]
        )

        for performance in performances or []:
            performance.create(production)

        CastMember.objects.bulk_create(
            [cast_member.to_obj(production) for cast_member in cast or []]
        )

        CrewMember.objects.bulk_create(
            [cast_member.to_obj(production) for cast_member in crew or []]
        )

        ProductionTeamMember.objects.bulk_create(
            [
                production_team_member.to_obj(production)
                for production_team_member in production_team or []
            ]
        )

        return CreateProduction(production=production)


class Mutation(graphene.ObjectType):
    create_production = CreateProduction.Field()
