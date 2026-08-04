from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from cookbook.helper.permission_helper import has_group_permission
from cookbook.models import Recipe

from .pdf_writer import PDFDocument


def _user_can_view_recipe(request, recipe):
    if recipe.private:
        return recipe.created_by == request.user or request.user in recipe.shared.all()
    return has_group_permission(request.user, ['guest', 'user'])


def _recipe_image_jpeg(recipe):
    if not recipe.image:
        return None
    try:
        from PIL import Image
        with recipe.image.open('rb') as f:
            img = Image.open(f)
            img.load()
        img = img.convert('RGB')
        img.thumbnail((900, 900))
        buf = BytesIO()
        img.save(buf, format='JPEG', quality=85)
        return buf.getvalue(), img.width, img.height
    except Exception:
        # A missing/corrupt/unreadable image shouldn't block getting the
        # rest of the recipe as a PDF.
        return None


def _ingredient_line(ingredient):
    if ingredient.no_amount:
        amount = ''
    else:
        unit = f' {ingredient.unit.name}' if ingredient.unit else ''
        amount = f'{ingredient.amount:g}{unit}'
    food = ingredient.food.name if ingredient.food else ''
    note = f' ({ingredient.note})' if ingredient.note else ''
    return amount, f'{food}{note}'


@login_required
def export_recipe_pdf(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, space=request.space)

    if not _user_can_view_recipe(request, recipe):
        raise PermissionDenied()

    steps = recipe.steps.order_by('order', 'pk').prefetch_related('ingredients__food', 'ingredients__unit')

    doc = PDFDocument()
    doc.heading(recipe.name, size=18)

    meta_bits = [f'Servings: {recipe.servings}']
    if recipe.servings_text:
        meta_bits.append(recipe.servings_text)
    if recipe.working_time:
        meta_bits.append(f'Prep: {recipe.working_time} min')
    if recipe.waiting_time:
        meta_bits.append(f'Cook/Wait: {recipe.waiting_time} min')
    doc.paragraph('   '.join(meta_bits), size=9)

    image = _recipe_image_jpeg(recipe)
    if image:
        jpeg_bytes, width, height = image
        doc.image(jpeg_bytes, width, height)

    if recipe.description:
        doc.paragraph(recipe.description, size=10)

    doc.rule()
    doc.heading('Ingredients', size=13)
    for step in steps:
        for ingredient in step.ingredients.all():
            if ingredient.is_header:
                doc.paragraph(ingredient.note or '', size=10, bold=True)
                continue
            amount, food = _ingredient_line(ingredient)
            doc.two_column_line(amount, food, size=10)

    doc.rule()
    doc.heading('Instructions', size=13)
    for i, step in enumerate(steps, start=1):
        label = f'{i}. {step.name}' if step.name else f'Step {i}'
        doc.paragraph(label, size=10, bold=True)
        doc.paragraph(step.instruction, size=10)

    if recipe.nutrition:
        doc.rule()
        doc.heading('Nutrition', size=13)
        doc.two_column_line('Calories', f'{recipe.nutrition.calories:g}', size=10)
        doc.two_column_line('Fats', f'{recipe.nutrition.fats:g} g', size=10)
        doc.two_column_line('Carbohydrates', f'{recipe.nutrition.carbohydrates:g} g', size=10)
        doc.two_column_line('Proteins', f'{recipe.nutrition.proteins:g} g', size=10)

    pdf_bytes = doc.to_bytes()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{recipe.name}.pdf"'
    return response
