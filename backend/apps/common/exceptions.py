from rest_framework.exceptions import APIException


class InsufficientStock(APIException):
    status_code = 409
    default_detail = "Недостаточно остатка на складе."
    default_code = "insufficient_stock"


class PayloadTooLarge(APIException):
    status_code = 413
    default_detail = "Файл слишком большой."
    default_code = "payload_too_large"
