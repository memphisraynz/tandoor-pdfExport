from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tandoor_pdfexport', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='pdfexportsettings',
            name='ingredient_grouping',
            field=models.CharField(
                choices=[('per_step', 'Grouped by step'), ('consolidated', 'One combined list')],
                default='per_step',
                max_length=16,
            ),
        ),
        migrations.AlterField(
            model_name='pdfexportsettings',
            name='font',
            field=models.CharField(
                choices=[
                    ('serif', 'Serif (Gloock + Lora + IBM Plex Mono)'),
                    ('helvetica', 'Helvetica'),
                    ('times', 'Times'),
                    ('courier', 'Courier'),
                ],
                default='serif',
                max_length=16,
            ),
        ),
    ]
