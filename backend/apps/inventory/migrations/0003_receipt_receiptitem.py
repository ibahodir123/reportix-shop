import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_initial'),
        ('inventory', '0002_initial'),
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Receipt',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('supplier_name', models.CharField(blank=True, max_length=255, verbose_name='Поставщик')),
                ('reference', models.CharField(blank=True, max_length=255, verbose_name='Основание')),
                ('client_uuid', models.UUIDField(blank=True, null=True)),
                ('total_cost', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='receipts', to=settings.AUTH_USER_MODEL)),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='tenants.tenant')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='receipts', to='inventory.warehouse')),
            ],
            options={
                'verbose_name': 'Приёмка',
                'verbose_name_plural': 'Приёмки',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ReceiptItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=3, max_digits=18)),
                ('purchase_price', models.DecimalField(decimal_places=2, max_digits=18)),
                ('total', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('movement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='receipt_items', to='inventory.stockmovement')),
                ('receipt', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='inventory.receipt')),
                ('variant', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='receipt_items', to='catalog.variant')),
            ],
            options={
                'verbose_name': 'Позиция приёмки',
                'verbose_name_plural': 'Позиции приёмки',
            },
        ),
        migrations.AddConstraint(
            model_name='receipt',
            constraint=models.UniqueConstraint(condition=models.Q(('client_uuid__isnull', False)), fields=('tenant', 'client_uuid'), name='uniq_receipt_client_uuid_per_tenant'),
        ),
    ]
