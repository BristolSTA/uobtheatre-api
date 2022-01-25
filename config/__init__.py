from celery import states

from .celery import app as celery_app

# Override celery task states to include skipped
new_states = set(states.ALL_STATES)
new_states.add("SKIPPED")
states.ALL_STATES = new_states

__all__ = ("celery_app",)
