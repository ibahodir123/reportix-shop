from django.db import models


class TimeStampedModel(models.Model):
    """Базовые метки времени для всех сущностей."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class TenantOwnedModel(TimeStampedModel):
    """
    Базовая модель, привязанная к тенанту (единица изоляции SaaS).

    Любая доменная сущность наследуется отсюда, а querysets в API
    фильтруются по request.tenant (см. apps.common.api.TenantScopedViewSet).
    """

    tenant = models.ForeignKey(
        "tenants.Tenant",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)s_set",
    )

    class Meta:
        abstract = True
