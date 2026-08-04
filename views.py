import json
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_http_methods

from cookbook.helper.permission_helper import has_group_permission
from cookbook.models import Recipe

from .pdf_writer import ACCENT, PDFDocument

IMAGE_BOX = (190, 150)


def _user_can_view_recipe(request, recipe):
    if recipe.private:
        return recipe.created_by == request.user or request.user in recipe.shared.all()
    return has_group_permission(request.user, ['guest', 'user'])


def _hex_to_rgb(hex_color):
    hex_color = (hex_color or '').lstrip('#')
    if len(hex_color) != 6:
        return ACCENT
    try:
        return tuple(int(hex_color[i:i + 2], 16) / 255 for i in (0, 2, 4))
    except ValueError:
        return ACCENT


def _get_preferences(request):
    """(font, accent_rgb, image_style, ingredient_grouping) for this user,
    falling back to defaults if they've never saved preferences (or the
    settings table somehow isn't there, e.g. mid-upgrade before migrations
    ran)."""
    try:
        from .models import PdfExportSettings
        obj = PdfExportSettings.objects.filter(user=request.user).first()
    except Exception:
        obj = None
    if not obj:
        return 'serif', ACCENT, 'cropped', 'per_step'
    return obj.font, _hex_to_rgb(obj.accent_color), obj.image_style, obj.ingredient_grouping


def _recipe_image_jpeg(recipe, image_style='cropped', max_size=900):
    if not recipe.image:
        return None
    try:
        from PIL import Image
        with recipe.image.open('rb') as f:
            img = Image.open(f)
            img.load()
        img = img.convert('RGB')
        if image_style == 'cropped':
            target_ratio = IMAGE_BOX[0] / IMAGE_BOX[1]
            w, h = img.size
            current_ratio = w / h
            if current_ratio > target_ratio:
                new_w = int(h * target_ratio)
                offset = (w - new_w) // 2
                img = img.crop((offset, 0, offset + new_w, h))
            else:
                new_h = int(w / target_ratio)
                offset = (h - new_h) // 2
                img = img.crop((0, offset, w, offset + new_h))
        img.thumbnail((max_size, max_size))
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


def _ingredient_tuple(ingredient):
    """(amount, food, is_header) - the shape step_block() expects."""
    if ingredient.is_header:
        return '', ingredient.note or '', True
    if ingredient.no_amount:
        amount = ''
    else:
        unit = f' {ingredient.unit.name}' if ingredient.unit else ''
        amount = f'{_fmt_amount(ingredient.amount)}{unit}'
    food = ingredient.food.name if ingredient.food else ''
    note = f' ({ingredient.note})' if ingredient.note else ''
    return amount, f'{food}{note}', False


@login_required
def recipe_picker(request):
    """Plain server-rendered search page - deliberately not part of the Vue
    frontend. It works through the exact same request/response path as
    export_recipe_pdf below (already confirmed working), so it doesn't
    depend on the Vite build, PLUGINS_BUILD, collectstatic, or any browser/
    service-worker/CDN caching of the SPA bundle.
    """
    query = request.GET.get('q', '').strip()
    recipes = []
    if query:
        candidates = Recipe.objects.filter(space=request.space, name__icontains=query).order_by('name')[:50]
        recipes = [r for r in candidates if _user_can_view_recipe(request, r)]
    return render(request, 'tandoor-pdfExport/recipe_picker.html', {'query': query, 'recipes': recipes})


@login_required
@require_http_methods(['GET', 'POST'])
def settings_api(request):
    from .models import (
        FONT_CHOICES,
        IMAGE_STYLE_CHOICES,
        INGREDIENT_GROUPING_CHOICES,
        PdfExportSettings,
    )

    obj, _ = PdfExportSettings.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        try:
            data = json.loads(request.body or '{}')
        except ValueError:
            data = {}
        if data.get('font') in dict(FONT_CHOICES):
            obj.font = data['font']
        accent = data.get('accent_color')
        if isinstance(accent, str) and len(accent.lstrip('#')) == 6:
            obj.accent_color = accent if accent.startswith('#') else f'#{accent}'
        if data.get('image_style') in dict(IMAGE_STYLE_CHOICES):
            obj.image_style = data['image_style']
        if data.get('ingredient_grouping') in dict(INGREDIENT_GROUPING_CHOICES):
            obj.ingredient_grouping = data['ingredient_grouping']
        obj.save()
    return JsonResponse({
        'font': obj.font,
        'accent_color': obj.accent_color,
        'image_style': obj.image_style,
        'ingredient_grouping': obj.ingredient_grouping,
        'font_choices': FONT_CHOICES,
        'image_style_choices': IMAGE_STYLE_CHOICES,
        'ingredient_grouping_choices': INGREDIENT_GROUPING_CHOICES,
    })


@login_required
def export_recipe_pdf(request, pk):
    recipe = get_object_or_404(Recipe, pk=pk, space=request.space)

    if not _user_can_view_recipe(request, recipe):
        raise PermissionDenied()

    font, accent, image_style, ingredient_grouping = _get_preferences(request)

    steps = recipe.steps.order_by('order', 'pk').prefetch_related('ingredients__food', 'ingredients__unit')

    spec_cells = [('Servings', f'{recipe.servings}{" " + recipe.servings_text if recipe.servings_text else ""}')]
    if recipe.working_time:
        spec_cells.append(('Prep', f'{recipe.working_time} min'))
    if recipe.waiting_time:
        spec_cells.append(('Bake', f'{recipe.waiting_time} min'))

    image = _recipe_image_jpeg(recipe, image_style=image_style)

    image_box = IMAGE_BOX
    if image and image_style != 'cropped':
        # Not cropping to IMAGE_BOX's aspect ratio here, so placing the raw
        # image at that fixed box would stretch/squash it - fit it into a
        # same-ish-sized box instead, preserving its real aspect ratio.
        _, real_w, real_h = image
        max_w, max_h = IMAGE_BOX
        scale = min(max_w / real_w, max_h / real_h, 1)
        image_box = (real_w * scale, real_h * scale)

    doc = PDFDocument(footer_label=recipe.name, accent=accent, font=font)
    doc.header_block(
        recipe.name,
        recipe.description,
        image=image,
        image_box=image_box,
    )
    doc.spec_band(spec_cells)

    if ingredient_grouping == 'consolidated':
        all_ingredients = [
            _ingredient_tuple(ingredient)
            for step in steps
            for ingredient in step.ingredients.all()
        ]
        if all_ingredients:
            doc.heading('Ingredients')
            doc.ingredient_checklist(all_ingredients)
        doc.heading('Instructions')
        for i, step in enumerate(steps, start=1):
            doc.instruction_step(i, step.name, step.instruction)
    else:
        for i, step in enumerate(steps, start=1):
            ingredients = [_ingredient_tuple(ingredient) for ingredient in step.ingredients.all()]
            doc.step_block(i, step.name, ingredients, step.instruction)

    if recipe.nutrition:
        doc.heading('Nutrition')
        doc.two_column_line('Calories', _fmt_amount(recipe.nutrition.calories), size=10)
        doc.two_column_line('Fats', f'{_fmt_amount(recipe.nutrition.fats)} g', size=10)
        doc.two_column_line('Carbohydrates', f'{_fmt_amount(recipe.nutrition.carbohydrates)} g', size=10)
        doc.two_column_line('Proteins', f'{_fmt_amount(recipe.nutrition.proteins)} g', size=10)

    pdf_bytes = doc.to_bytes()

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{recipe.name}.pdf"'
    return response
