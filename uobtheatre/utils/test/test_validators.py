from types import SimpleNamespace
from uobtheatre.utils.validators import RequiredFieldValidator


def test_and_validator():
    obj = SimpleNamespace(a=1)
    validator = RequiredFieldValidator(["a"])
    assert validator.validate(obj)
