from django.apps import AppConfig


class PdfExportConfig(AppConfig):
    website = 'https://github.com/memphisraynz/tandoor-pdfExport'
    github = 'https://github.com/memphisraynz/tandoor-pdfExport'

    default_auto_field = 'django.db.models.BigAutoField'
    # Resolves at import time to wherever this actually got cloned to
    # (e.g. 'recipes.plugins.tandoor-pdfExport' if cloned under its GitHub
    # repo name) instead of hardcoding a folder name that has to match
    # exactly - Django requires this to be the real importable path of
    # wherever the plugin's directory lives on disk.
    name = __package__
    # Django app labels must be valid Python identifiers (letters/digits/
    # underscore only) - the actual repo/folder name (tandoor-pdfExport)
    # has a hyphen and isn't valid here, so this is set explicitly rather
    # than left to derive from `name`. Purely an internal Django registry
    # key, never shown anywhere in the UI.
    label = 'tandoor_pdfexport'
    verbose_name = 'PDF Export'
    base_url = 'pdf-export/'
    # Name of the DRF router in urls.py that the core API router should extend.
    # We don't register any viewsets on it, but cookbook/urls.py does a
    # pydoc.locate() lookup on this name for every plugin, so it must exist.
    api_router_name = 'pdf_export_router'

    disabled = False
