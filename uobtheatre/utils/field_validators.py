from django.core.validators import URLValidator


class OptionalSchemeURLValidator(URLValidator):
    def __call__(self, value):
        if "://" not in value:
            # Validate as if it were http://
            value = "http://" + value
        super().__call__(value)
