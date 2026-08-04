from django.conf import settings
from django.db import models

FONT_CHOICES = [
    ('helvetica', 'Helvetica'),
    ('times', 'Times'),
    ('courier', 'Courier'),
]

IMAGE_STYLE_CHOICES = [
    ('cropped', 'Cropped'),
    ('full', 'Full image'),
]


class PdfExportSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pdf_export_settings')
    font = models.CharField(max_length=16, choices=FONT_CHOICES, default='helvetica')
    accent_color = models.CharField(max_length=7, default='#b85c1a')
    image_style = models.CharField(max_length=16, choices=IMAGE_STYLE_CHOICES, default='cropped')
