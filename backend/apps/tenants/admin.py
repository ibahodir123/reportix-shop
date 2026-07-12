from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Branch, Membership, Tenant, User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (("Дополнительно", {"fields": ("phone",)}),)
    list_display = ("username", "email", "phone", "is_staff")


class MembershipInline(admin.TabularInline):
    model = Membership
    extra = 0
    autocomplete_fields = ("user", "branch")


class BranchInline(admin.TabularInline):
    model = Branch
    extra = 0


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "inn", "owner", "is_active", "created_at")
    search_fields = ("name", "inn")
    inlines = (BranchInline, MembershipInline)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ("name", "tenant", "is_active")
    list_filter = ("tenant", "is_active")
    search_fields = ("name",)


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "tenant", "role", "branch")
    list_filter = ("tenant", "role")
    autocomplete_fields = ("user", "tenant", "branch")
