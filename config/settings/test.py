import tempfile

from .local import *  # noqa: F403,F401

MEDIA_ROOT = tempfile.mkdtemp()
