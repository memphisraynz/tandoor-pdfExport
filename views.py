from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404

from cookbook.helper.permission_helper import has_group_permission
from cookbook.models import Recipe

from .pdf_writer import ACCENT, MUTED, PDFDocument, text_width


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


def _fmt_amount(value):
    # ingredient.amount / nutrition fields are Decimal(decimal_places=16) -
    # Decimal's :g format keeps every stored trailing zero (unlike float's),
    # so e.g. 1 comes out as "1.0000000000000000". Round-tripping through
    # float first gives the same trailing-zero-stripping behaviour a user
    # actually wants here.
    return f'{float(value):g}'


def _ingredient_row(ingredient):
    if ingredient.no_amount:
        amount = ''
    else:
        unit = f' {ingredient.unit.name}' if ingredient.unit else ''
        amount = f'{_fmt_amount(ingredient.amount)}{unit}'
    food = ingredient.food.name if ingredient.food else ''
    note = f' ({ingredient.note})' if ingredient.note else ''
    return amount, f'{food}{note}'


@login_required
def export_recipe_pdf(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, space=request.space)

    if not _user_can_view_recipe(request, recipe):
        raise PermissionDenied()

    steps = recipe.steps.order_by('order', 'pk').prefetch_related('ingredients__food', 'ingredients__unit')

    doc = PDFDocument(footer_label=recipe.name)
    doc.heading(recipe.name, size=20)

    meta_bits = [f'Servings: {recipe.servings}']
    if recipe.servings_text:
        meta_bits.append(recipe.servings_text)
    if recipe.working_time:
        meta_bits.append(f'Prep: {recipe.working_time} min')
    if recipe.waiting_time:
        meta_bits.append(f'Cook/Wait: {recipe.waiting_time} min')
    doc.paragraph('   •   '.join(meta_bits), size=9.5, color=MUTED)

    image = _recipe_image_jpeg(recipe)
    if image:
        jpeg_bytes, width, height = image
        doc.image(jpeg_bytes, width, height)

    if recipe.description:
        doc.paragraph(recipe.description, size=10.5, italic=True, color=MUTED)

    doc.rule()
    doc.heading('Ingredients', size=13)

    ingredient_rows = []
    for step in steps:
        for ingredient in step.ingredients.all():
            if ingredient.is_header:
                ingredient_rows.append((True, ingredient.note or ''))
            else:
                ingredient_rows.append((False, _ingredient_row(ingredient)))

    # Size the amount column to the longest amount actually in this recipe
    # rather than a fixed guess - otherwise a long amount string (or an
    # unexpected unit name) draws into the ingredient name next to it.
    amount_col_width = 60
    for is_header, row in ingredient_rows:
        if not is_header:
            amount_col_width = max(amount_col_width, text_width(row[0], 10, bold=True) + 12)

    for is_header, row in ingredient_rows:
        if is_header:
            doc.paragraph(row, size=10, bold=True)
        else:
            amount, food = row
            doc.two_column_line(amount, food, size=10, col_width=amount_col_width, left_color=ACCENT)

    doc.rule()
    doc.heading('Instructions', size=13)
    for i, step in enumerate(steps, start=1):
        label = f'{i}. {step.name}' if step.name else f'Step {i}'
        doc.paragraph(label, size=10, bold=True)
        doc.paragraph(step.instruction, size=10)

    if recipe.nutrition:
        doc.rule()
        doc.heading('Nutrition', size=13)
        doc.two_column_line('Calories', _fmt_amount(recipe.nutrition.calories), size=10)
        doc.two_column_line('Fats', f'{_fmt_amount(recipe.nutrition.fats)} g', size=10)
        doc.two_column_line('Carbohydrates', f'{_fmt_amount(recipe.nutrition.carbohydrates)} g', size=10)
        doc.two_column_line('Proteins', f'{_fmt_amount(recipe.nutrition.proteins)} g', size=10)

    pdf_bytes = doc.to_bytes()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{recipe.name}.pdf"'
    return response
