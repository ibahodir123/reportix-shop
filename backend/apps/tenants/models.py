from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.common.models import TimeStampedModel


class User(AbstractUser):
    """Пользователь системы. Принадлежность к бизнесам — через Membership."""

    phone = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return self.username


class Tenant(TimeStampedModel):
    """Бизнес-аккаунт (розничная компания) — единица изоляции SaaS."""

    name = models.CharField(max_length=255, verbose_name="Наименование")
    inn = models.CharField(max_length=9, blank=True, null=True, verbose_name="ИНН")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон")
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    owner = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="owned_tenants", verbose_name="Владелец"
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Бизнес"
        verbose_name_plural = "Бизнесы"

    def __str__(self):
        return self.name


class Branch(TimeStampedModel):
    """Магазин / филиал внутри бизнеса."""

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="branches")
    name = models.CharField(max_length=255, verbose_name="Наименование")
    address = models.TextField(blank=True, null=True, verbose_name="Адрес")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Телефон")
    is_active = models.BooleanField(default=True, verbose_name="Активен")

    class Meta:
        ordering = ["name"]
        unique_together = ("tenant", "name")
        verbose_name = "Магазин"
        verbose_name_plural = "Магазины"

    def __str__(self):
        return self.name


class Membership(models.Model):
    """Членство пользователя в бизнесе с ролью и (для кассира) магазином."""

    ROLE_OWNER = "owner"
    ROLE_MANAGER = "manager"
    ROLE_CASHIER = "cashier"
    ROLE_CHOICES = (
        (ROLE_OWNER, "Владелец"),
        (ROLE_MANAGER, "Менеджер"),
        (ROLE_CASHIER, "Кассир"),
    )

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_CASHIER)
    branch = models.ForeignKey(
        Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name="memberships"
    )

    class Meta:
        unique_together = ("tenant", "user")
        verbose_name = "Членство"
        verbose_name_plural = "Членства"

    def __str__(self):
        return f"{self.user} @ {self.tenant} ({self.get_role_display()})"
