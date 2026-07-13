import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('catalog', '0002_initial'),
        ('inventory', '0002_initial'),
        ('sales', '0002_initial'),
        ('tenants', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Return',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('client_uuid', models.UUIDField(blank=True, null=True)),
                ('payment_type', models.CharField(choices=[('cash', 'Наличные'), ('card', 'Карта'), ('mixed', 'Смешанная')], default='cash', max_length=10)),
                ('refund_cash', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('refund_card', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('refund_total', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('branch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='returns', to='tenants.branch')),
                ('created_by', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='returns', to=settings.AUTH_USER_MODEL)),
                ('sale', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='returns', to='sales.sale')),
                ('shift', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='returns', to='sales.cashiershift')),
                ('tenant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='%(app_label)s_%(class)s_set', to='tenants.tenant')),
                ('warehouse', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='returns', to='inventory.warehouse')),
            ],
            options={
                'verbose_name': 'Возврат',
                'verbose_name_plural': 'Возвраты',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ReturnItem',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('quantity', models.DecimalField(decimal_places=3, max_digits=18)),
                ('price', models.DecimalField(decimal_places=2, max_digits=18)),
                ('total', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
                ('document', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='sales.return')),
                ('movement', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='return_items', to='inventory.stockmovement')),
                ('sale_item', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='returns', to='sales.saleitem')),
                ('variant', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='return_items', to='catalog.variant')),
            ],
            options={
                'verbose_name': 'Позиция возврата',
                'verbose_name_plural': 'Позиции возврата',
            },
        ),
        migrations.AddConstraint(
            model_name='return',
            constraint=models.UniqueConstraint(condition=models.Q(('client_uuid__isnull', False)), fields=('tenant', 'client_uuid'), name='uniq_return_client_uuid_per_tenant'),
        ),
    ]
