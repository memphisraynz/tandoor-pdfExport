import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='PdfExportSettings',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('font', models.CharField(choices=[('helvetica', 'Helvetica'), ('times', 'Times'), ('courier', 'Courier')], default='helvetica', max_length=16)),
                ('accent_color', models.CharField(default='#b85c1a', max_length=7)),
                ('image_style', models.CharField(choices=[('cropped', 'Cropped'), ('full', 'Full image')], default='cropped', max_length=16)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='pdf_export_settings', to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
