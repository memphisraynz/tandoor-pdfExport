from django.conf import settings
from django.db import models

FONT_CHOICES = [
    ('serif', 'Serif (Gloock + Lora + IBM Plex Mono)'),
    ('helvetica', 'Helvetica'),
    ('times', 'Times'),
    ('courier', 'Courier'),
]

IMAGE_STYLE_CHOICES = [
    ('cropped', 'Cropped'),
    ('full', 'Full image'),
]

INGREDIENT_GROUPING_CHOICES = [
    ('per_step', 'Grouped by step'),
    ('consolidated', 'One combined list'),
]

NOTE_STYLE_CHOICES = [
    ('none', 'No prefix'),
    ('note', '"Note:" prefix'),
    ('nb', '"NB:" prefix'),
]
NOTE_PREFIX_TEXT = {
    'none': '',
    'note': 'Note:',
    'nb': 'NB:',
}


class PdfExportSettings(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='pdf_export_settings')
    font = models.CharField(max_length=16, choices=FONT_CHOICES, default='serif')
    accent_color = models.CharField(max_length=7, default='#b85c1a')
    image_style = models.CharField(max_length=16, choices=IMAGE_STYLE_CHOICES, default='cropped')
    ingredient_grouping = models.CharField(max_length=16, choices=INGREDIENT_GROUPING_CHOICES, default='per_step')
    note_style = models.CharField(max_length=16, choices=NOTE_STYLE_CHOICES, default='none')
