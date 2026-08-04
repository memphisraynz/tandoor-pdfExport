from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string

from cookbook.helper.permission_helper import has_group_permission
from cookbook.models import Recipe


def _user_can_view_recipe(request, recipe):
    if recipe.private:
        return recipe.created_by == request.user or request.user in recipe.shared.all()
    return has_group_permission(request.user, ['guest', 'user'])


@login_required
def export_recipe_pdf(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, space=request.space)

    if not _user_can_view_recipe(request, recipe):
        raise PermissionDenied()

    steps = recipe.steps.order_by('order', 'pk').prefetch_related('ingredients__food', 'ingredients__unit')

    html = render_to_string('pdf_export_plugin/recipe_pdf.html', {
        'recipe': recipe,
        'steps': steps,
    })

    # Imported lazily so a missing/not-yet-installed dependency doesn't break
    # plugin loading (and the rest of Tandoor) at Django startup.
    from weasyprint import HTML
    pdf_bytes = HTML(string=html, base_url=request.build_absolute_uri('/')).write_pdf()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{recipe.name}.pdf"'
    return response
