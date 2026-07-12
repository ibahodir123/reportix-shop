def lock_tenant(tenant):
    """
    Блокирует строку тенанта (SELECT ... FOR UPDATE), сериализуя операции
    внутри одного тенанта: устраняет гонки нумерации чеков, client_uuid и
    автогенерации SKU. Вызывать внутри transaction.atomic().

    Порядок блокировок всегда: сначала tenant, затем stock — чтобы не было
    взаимных блокировок между параллельными операциями.
    """
    from apps.tenants.models import Tenant

    return Tenant.objects.select_for_update().get(pk=tenant.pk)
