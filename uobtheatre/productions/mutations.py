import graphene

from uobtheatre.discounts.models import Discount, DiscountRequirement
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
            capacity=self.capacity
            if self.capacity is not None
            else seat_group.capacity,
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


class ConcessionTypeInput(graphene.InputObjectType):
    name = graphene.String()
    description = graphene.String()


class DiscountRequirementInput(graphene.InputObjectType):
    number = graphene.Int()
    concession_type = graphene.Field(ConcessionTypeInput)

    def to_obj(self):
        return DiscountRequirement(
            number=self.number, concession_type=self.concession_type
        )


class DiscountInput(graphene.InputObjectType):
    name = graphene.String()
    percentage = graphene.Float()
    requirements = graphene.List(DiscountRequirementInput)

    def create(self, performances):
        discount = Discount.objects.create(
            name=self.name,
            percentage=self.percentage,
        )
        discount.performances.add(*performances)

        DiscountRequirement.bulk_create(
            [
                DiscountRequirement(number=requirement.number)
                for requirement in self.requirements or []
            ]
        )
        return discount


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

        discounts = graphene.List(DiscountInput)

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
        discounts=None,
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

        created_performances = [
            performance.create(production) for performance in performances or []
        ]

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

        # Create discounts and assign to all performances
        for discount in discounts or []:
            discount.create(created_performances)

        return CreateProduction(production=production)


class Mutation(graphene.ObjectType):
    create_production = CreateProduction.Field()
