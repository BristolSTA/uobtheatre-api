import uuid

from django.db import models
from django.template.defaultfilters import slugify
from django.utils import timezone
from django.utils.functional import cached_property

from uobtheatre.societies.models import Society
from uobtheatre.utils.models import SoftDeletionMixin, TimeStampedMixin
from uobtheatre.venues.models import SeatGroup, Venue


class CrewRole(models.Model):
    """Crew role"""

    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class Warning(models.Model):
    """A venue is a space often where shows take place"""

    warning = models.CharField(max_length=255)

    def __str__(self):
        return self.warning


class Production(models.Model, SoftDeletionMixin, TimeStampedMixin):
    """A production is a show (like the 2 weeks things) and can have many
    performaces (these are like the nights).
    """

    name = models.CharField(max_length=255)
    subtitle = models.CharField(max_length=255, null=True)
    description = models.TextField(null=True)

    society = models.ForeignKey(Society, on_delete=models.SET_NULL, null=True)

    poster_image = models.ImageField(null=True)
    featured_image = models.ImageField(null=True)
    cover_image = models.ImageField(null=True)

    age_rating = models.SmallIntegerField(null=True)
    facebook_event = models.CharField(max_length=255, null=True)

    warnings = models.ManyToManyField(Warning)

    def __str__(self):
        return self.name

    def is_upcoming(self) -> bool:
        """
        Returns if the show is upcoming. If the show has no upcoming
        productions (not ended) then it is not upcoming.
        """
        performances = self.performances.all()
        return any(performance.start > timezone.now() for performance in performances)

    def end_date(self):
        """
        Return when the last performance ends.
        """
        performances = self.performances.all()
        if not performances:
            return None
        return max(performance.end for performance in performances)

    def start_date(self):
        """
        Return when the first performance starts.
        """
        performances = self.performances.all()
        if not performances:
            return None
        return min(performance.start for performance in performances)

    def duration(self):
        """
        Returns the duration of the shortest show as a datetime object.
        """
        performances = self.performances.all()
        if not performances:
            return None
        return min(performance.duration() for performance in performances)

    def slug(self):
        """ Generate a slug for this production """
        # TODO axe this for auto slug
        return (
            slugify(self.name + "-" + str(self.start_date().year))
            if self.start_date()
            else slugify(self.name + "-" + str(self.id))
        )


class CastMember(models.Model):
    """Member of production cast"""

    name = models.CharField(max_length=255)
    profile_picture = models.ImageField(null=True, blank=True)
    role = models.CharField(max_length=255, null=True)
    production = models.ForeignKey(
        Production, on_delete=models.CASCADE, related_name="cast"
    )

    def __str__(self):
        return self.name


class CrewMember(models.Model):
    """Member of production crew"""

    name = models.CharField(max_length=255)
    role = models.ForeignKey(CrewRole, null=True, on_delete=models.SET_NULL)
    production = models.ForeignKey(
        Production, on_delete=models.CASCADE, related_name="crew"
    )

    def __str__(self):
        return self.name


class Performance(models.Model, SoftDeletionMixin, TimeStampedMixin):
    """A performance is a discrete event when the show takes place eg 7pm on
    Tuesday.
    """

    production = models.ForeignKey(
        Production, on_delete=models.CASCADE, related_name="performances"
    )

    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True)
    start = models.DateTimeField(null=True)
    end = models.DateTimeField(null=True)

    extra_information = models.TextField(null=True, blank=True)

    def seat_bookings(self):
        """ Get all seat bookings for this show """
        return self.bookings.seat_bookings.all()

    # @cached_property
    def capacity_remaining(self):
        """
        Returns the capacity remaining for a given seat group
        """
        return sum()

    def seat_group_capacity(self, seat_group: SeatGroup):
        """
        Given a seat group, returns the capacity of that seat group for this
        show.
        """
        return seat_group.capacity - self.bookings.filter()

    def duration(self):
        """
        Returns the duration of the show as a datetime object
        """
        return self.end - self.start

    def __str__(self):
        if self.start is None:
            return f"Perforamce of {self.production.name}"
        return f"Perforamce of {self.production.name} at {self.start.strftime('%H:%M')} on {self.start.strftime('%m/%d/%Y')}"
