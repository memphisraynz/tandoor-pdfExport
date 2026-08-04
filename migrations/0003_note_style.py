from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tandoor_pdfexport', '0002_ttf_fonts_and_grouping'),
    ]

    operations = [
        migrations.AddField(
            model_name='pdfexportsettings',
            name='note_style',
            field=models.CharField(
                choices=[('none', 'No prefix'), ('note', '"Note:" prefix'), ('nb', '"NB:" prefix')],
                default='none',
                max_length=16,
            ),
        ),
    ]
