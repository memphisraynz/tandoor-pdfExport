from django.urls import path
from rest_framework import routers

from . import views

# Unused but required - see the comment on api_router_name in apps.py.
pdf_export_router = routers.DefaultRouter()

urlpatterns = [
    path('recipe/<int:pk>/pdf/', views.export_recipe_pdf, name='pdf_export_recipe'),
]
