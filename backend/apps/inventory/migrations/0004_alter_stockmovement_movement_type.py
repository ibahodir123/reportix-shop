from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0003_receipt_receiptitem'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stockmovement',
            name='movement_type',
            field=models.CharField(
                choices=[
                    ('in', 'Приход'),
                    ('out', 'Расход'),
                    ('writeoff', 'Списание'),
                    ('transfer', 'Перемещение'),
                    ('adjust', 'Корректировка'),
                    ('return_in', 'Возврат от покупателя'),
                ],
                max_length=16,
            ),
        ),
    ]
