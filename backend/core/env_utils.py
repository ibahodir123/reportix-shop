from django.core.exceptions import ImproperlyConfigured

INSECURE_DEFAULT = "dev-insecure-change-me"


def get_secret_key(value, debug):
    """
    Возвращает SECRET_KEY. В production (DEBUG=False) требует явно заданный
    безопасный ключ: пустое значение или небезопасный дефолт запрещены.
    """
    if not value:
        if debug:
            return INSECURE_DEFAULT
        raise ImproperlyConfigured(
            "SECRET_KEY must be set in production (DEBUG=False)."
        )
    if not debug and value == INSECURE_DEFAULT:
        raise ImproperlyConfigured(
            "SECRET_KEY must not use the insecure default value in production."
        )
    return value
