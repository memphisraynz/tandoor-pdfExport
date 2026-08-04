from django.apps import AppConfig


class PdfExportConfig(AppConfig):
    # Fill these in once you've pushed this to your own repo - they're only
    # used to render links on the Tandoor admin "System" page.
    website = 'https://github.com/YOUR_USERNAME/pdf_export_plugin'
    github = 'https://github.com/YOUR_USERNAME/pdf_export_plugin'

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'recipes.plugins.pdf_export_plugin'
    verbose_name = 'PDF Export'
    base_url = 'pdf-export/'
    # Name of the DRF router in urls.py that the core API router should extend.
    # We don't register any viewsets on it, but cookbook/urls.py does a
    # pydoc.locate() lookup on this name for every plugin, so it must exist.
    api_router_name = 'pdf_export_router'

    disabled = False
