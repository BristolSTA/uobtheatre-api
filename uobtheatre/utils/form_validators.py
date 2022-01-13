from django.core.validators import URLValidator


class OptionalSchemeURLValidator(URLValidator):
    """Validator that validates the value is a valid URL (with or without a HTTP scheme)"""

    def __init__(self):
        super().__init__(schemes=["http", "https"])

    def __call__(self, value):
        if not any(value.startswith(scheme) for scheme in self.schemes):
            value = f"https://{value}"
        super().__call__(value)
