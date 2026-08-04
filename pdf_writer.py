"""Minimal, dependency-free PDF writer.

Generates a recipe-shaped document (a title/description/image header
block, per-step ingredient-checklist + instruction two-column blocks, a
nutrition table, a page footer) directly as PDF bytes, using only the
Python standard library - no third-party PDF package and no system
library (Pango/Cairo/etc.) needs to be installed anywhere.

Two rendering modes:

- 'serif' (default): embeds real TrueType fonts (Gloock/Lora/IBM Plex
  Mono, all OFL-licensed, shipped in fonts/) as Type0/Identity-H CID
  fonts, parsed with nothing but `struct` (see ttf_font.py). Real glyph
  metrics mean genuinely accurate word-wrap, and a much wider character
  repertoire (Cyrillic, box-drawing, fraction glyphs) than the fallback
  below.
- 'helvetica' / 'times' / 'courier': the original standard-14 fallback,
  used automatically if the TTF files can't be loaded for any reason,
  and selectable directly since it produces a noticeably smaller PDF.
  WinAnsiEncoding (~cp1252) only; characters outside that range render
  as '?'. Word-wrap widths are an approximation (a small per-character
  table, not real metrics).

Not a general-purpose PDF library - just enough to lay out a recipe.
"""

import os
import zlib

from .ttf_font import TTFFont

PAGE_WIDTH = 595.28   # A4, in points (1/72 inch)
PAGE_HEIGHT = 841.89
MARGIN = 56.7         # ~2cm

BLACK = (0.13, 0.13, 0.13)
MUTED = (0.48, 0.48, 0.48)
ACCENT = (0.72, 0.36, 0.10)      # warm terracotta - default accent color
LIGHT_BORDER = (0.85, 0.82, 0.78)

# Standard-14 PDF fonts - fallback mode, no embedding needed.
FONT_FAMILIES = {
    'helvetica': ('Helvetica', 'Helvetica-Bold', 'Helvetica-Oblique'),
    'times': ('Times-Roman', 'Times-Bold', 'Times-Italic'),
    'courier': ('Courier', 'Courier-Bold', 'Courier-Oblique'),
}

# 'serif' mode - embedded TTFs, one role per (family, weight/style) slot.
FONT_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fonts')
FONT_FILES = {
    'display': 'Gloock-Regular.ttf',
    'body': 'Lora-Regular.ttf',
    'body_bold': 'Lora-Bold.ttf',
    'body_italic': 'Lora-Italic.ttf',
    'data': 'IBMPlexMono-Regular.ttf',
    'data_bold': 'IBMPlexMono-Bold.ttf',
}
ROLE_PDF_NAMES = {
    'display': 'Disp',
    'body': 'Body',
    'body_bold': 'BodyB',
    'body_italic': 'BodyI',
    'data': 'Mono',
    'data_bold': 'MonoB',
}

_TTF_CACHE = None


def _load_ttf_fonts():
    global _TTF_CACHE
    if _TTF_CACHE is None:
        loaded = {}
        for role, filename in FONT_FILES.items():
            loaded[role] = TTFFont(os.path.join(FONT_FILES_DIR, filename))
        _TTF_CACHE = loaded
    return _TTF_CACHE


def _resolve_role(family, bold, italic):
    if family == 'display':
        return 'display'
    if family == 'data':
        return 'data_bold' if bold else 'data'
    # family == 'body'
    if bold:
        return 'body_bold'
    if italic:
        return 'body_italic'
    return 'body'


_NARROW = set('iIl.,;:\'"|!fjt ')
_WIDE = set('mwMW@%')


def _approx_char_width(ch, size, bold, monospace=False):
    if monospace:
        return 0.6 * size
    if ch in _WIDE:
        w = 0.86
    elif ch in _NARROW:
        w = 0.30
    elif ch.isupper():
        w = 0.68
    else:
        w = 0.52
    if bold:
        w *= 1.06
    return w * size


def _approx_text_width(text, size, bold, monospace=False):
    return sum(_approx_char_width(c, size, bold, monospace) for c in text)


def text_width(text, size, bold=False):
    """Approximate width, for callers with no PDFDocument instance handy.
    Prefer PDFDocument._text_width when one is available - it uses real
    glyph metrics in 'serif' mode."""
    return _approx_text_width(text, size, bold)


def _wrap_generic(text, width_fn, max_width):
    """Word-wrap a single line (no embedded newlines) to fit max_width,
    given a callable that measures a string's width."""
    lines = []
    current = ''
    for word in text.split(' '):
        candidate = f'{current} {word}'.strip()
        if current and width_fn(candidate) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
        # Hard-break a single word/fragment that's wider than a whole line.
        while width_fn(current) > max_width and len(current) > 1:
            lo, hi = 1, len(current)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if width_fn(current[:mid]) <= max_width:
                    lo = mid
                else:
                    hi = mid - 1
            lines.append(current[:lo])
            current = current[lo:]
    if current or not lines:
        lines.append(current)
    return lines


def _pdf_text_bytes(text):
    # WinAnsiEncoding lines up with cp1252; anything outside it becomes '?'.
    # Escaping happens on the encoded bytes, not the original str, so this
    # can't be corrupted by a later re-encode of already-escaped text.
    raw = text.encode('cp1252', errors='replace')
    return raw.replace(b'\\', b'\\\\').replace(b'(', b'\\(').replace(b')', b'\\)')


def _color_op(color, op):
    r, g, b = color
    return f'{r:.3f} {g:.3f} {b:.3f} {op}'.encode('ascii')


def _text_op(x, y, text, size, font, color):
    """Standard-14 fallback: a literal WinAnsi string in parens."""
    return (
        _color_op(color, 'rg') + b' BT /' + font.encode('ascii')
        + f' {size:.1f} Tf {x:.2f} {y:.2f} Td ('.encode('ascii')
        + _pdf_text_bytes(text) + b') Tj ET'
    )


class PDFDocument:
    def __init__(self, footer_label=None, accent=ACCENT, font='serif'):
        self._page_contents = []   # list of bytes, one per completed page
        self._images = []          # list of (jpeg_bytes, width, height)
        self._ops = []             # list of bytes, current page's operators
        self._y = PAGE_HEIGHT - MARGIN
        self.footer_label = footer_label
        self.accent = accent

        self.use_ttf = font == 'serif'
        if self.use_ttf:
            try:
                self._ttf_fonts = _load_ttf_fonts()
            except Exception:
                # Missing/corrupt font file - fall back to the standard-14
                # path rather than fail the whole export.
                self.use_ttf = False
                font = 'helvetica'
        if self.use_ttf:
            self._used_gids = {role: set() for role in FONT_FILES}
            self._gid_unicode = {role: {} for role in FONT_FILES}
        else:
            self.font_family = font if font in FONT_FAMILIES else 'helvetica'
            self._monospace = self.font_family == 'courier'

    # -- low level -----------------------------------------------------------
    def _new_page(self):
        self._page_contents.append(b'\n'.join(self._ops))
        self._ops = []
        self._y = PAGE_HEIGHT - MARGIN

    def _ensure_space(self, height):
        if self._y - height < MARGIN:
            self._new_page()

    def _text_width(self, text, size, bold=False, italic=False, family='body'):
        if self.use_ttf:
            role = _resolve_role(family, bold, italic)
            return self._ttf_fonts[role].text_width(text, size)
        return _approx_text_width(text, size, bold, self._monospace)

    def _wrap(self, text, size, bold, max_width, italic=False, family='body'):
        return _wrap_generic(
            text, lambda s: self._text_width(s, size, bold, italic, family), max_width
        )

    def _text_bytes(self, x, y, text, size, family='body', bold=False, italic=False, color=None):
        color = color if color is not None else BLACK
        if self.use_ttf:
            role = _resolve_role(family, bold, italic)
            font = self._ttf_fonts[role]
            used = self._used_gids[role]
            unicode_map = self._gid_unicode[role]
            gids = []
            for ch in text:
                gid = font.gid_for_char(ch)
                gids.append(gid)
                used.add(gid)
                if gid != 0:
                    unicode_map.setdefault(gid, ord(ch))
            hex_str = ''.join(f'{g:04X}' for g in gids)
            pdf_name = ROLE_PDF_NAMES[role]
            return (
                _color_op(color, 'rg') + b' BT /' + pdf_name.encode('ascii')
                + f' {size:.1f} Tf {x:.2f} {y:.2f} Td <'.encode('ascii')
                + hex_str.encode('ascii') + b'> Tj ET'
            )
        font_name = 'F2' if bold else ('F3' if italic else 'F1')
        return _text_op(x, y, text, size, font_name, color)

    def _draw_text(self, x, y, text, size, family='body', bold=False, italic=False, color=None):
        self._ops.append(self._text_bytes(x, y, text, size, family, bold, italic, color))

    # -- public layout API -----------------------------------------------------
    def heading(self, text, size=15, color=None, family='display'):
        color = color if color is not None else self.accent
        self._ensure_space(size * 1.8)
        self._y -= size
        self._draw_text(MARGIN, self._y, text, size, family=family, bold=True, color=color)
        self._y -= size * 0.7

    def paragraph(self, text, size=10, bold=False, italic=False, color=None, family='body'):
        max_width = PAGE_WIDTH - 2 * MARGIN
        line_height = size * 1.35
        for raw_line in (text or '').split('\n'):
            if not raw_line.strip():
                self._y -= line_height * 0.6
                continue
            for line in self._wrap(raw_line, size, bold, max_width, italic=italic, family=family):
                self._ensure_space(line_height)
                self._y -= line_height
                self._draw_text(MARGIN, self._y, line, size, family=family, bold=bold, italic=italic, color=color)

    def two_column_line(self, left, right, size=10, indent=0, col_width=95,
                         left_color=None, right_color=None, left_family='data', right_family='data'):
        max_width = PAGE_WIDTH - 2 * MARGIN - indent - col_width
        line_height = size * 1.45
        for i, line in enumerate(self._wrap(right, size, False, max_width, family=right_family)):
            self._ensure_space(line_height)
            self._y -= line_height
            if i == 0 and left:
                self._draw_text(MARGIN + indent, self._y, left, size, family=left_family, bold=True, color=left_color)
            self._draw_text(MARGIN + indent + col_width, self._y, line, size, family=right_family, color=right_color)

    def rule(self, color=None, thickness=1.2, gap_before=4, gap_after=10):
        color = color if color is not None else self.accent
        self._ensure_space(gap_before + gap_after)
        self._y -= gap_before
        r, g, b = color
        self._ops.append(
            f'{r:.3f} {g:.3f} {b:.3f} RG {thickness:.2f} w '
            f'{MARGIN:.2f} {self._y:.2f} m {PAGE_WIDTH - MARGIN:.2f} {self._y:.2f} l S'.encode('ascii')
        )
        self._y -= gap_after

    def _place_image(self, jpeg_bytes, real_w, real_h, x, y, w, h, border_color=LIGHT_BORDER):
        idx = len(self._images)
        self._images.append((jpeg_bytes, real_w, real_h))
        self._ops.append(f'q {w:.2f} 0 0 {h:.2f} {x:.2f} {y:.2f} cm /Im{idx} Do Q'.encode('ascii'))
        r, g, b = border_color
        self._ops.append(
            f'{r:.3f} {g:.3f} {b:.3f} RG 0.75 w {x:.2f} {y:.2f} {w:.2f} {h:.2f} re S'.encode('ascii')
        )

    def image(self, jpeg_bytes, width, height, max_width=None, max_height=220,
              gap_before=10, gap_after=14, border_color=LIGHT_BORDER):
        max_width = max_width or (PAGE_WIDTH - 2 * MARGIN)
        scale = min(max_width / width, max_height / height, 1)
        w, h = width * scale, height * scale
        self._ensure_space(gap_before + h + gap_after)
        self._y -= gap_before
        self._y -= h
        self._place_image(jpeg_bytes, width, height, MARGIN, self._y, w, h, border_color)
        self._y -= gap_after

    def header_block(self, title, meta_text, description, image=None, image_box=(190, 150), title_size=20):
        """Title/meta/description on the left, an image (already cropped by
        the caller to image_box's aspect ratio) on the right. `image` is
        (jpeg_bytes, real_width, real_height) or None.
        """
        content_width = PAGE_WIDTH - 2 * MARGIN
        gap = 20
        img_w, img_h = image_box if image else (0, 0)
        left_width = content_width - (img_w + gap if image else 0)

        title_line_h = title_size * 1.25
        title_lines = self._wrap(title, title_size, True, left_width, family='display')

        meta_size, meta_line_h = 9.5, 9.5 * 1.4
        meta_lines = self._wrap(meta_text, meta_size, False, left_width, family='data') if meta_text else []

        desc_size, desc_line_h = 10.5, 10.5 * 1.35
        desc_lines = []
        for raw in (description or '').split('\n'):
            if not raw.strip():
                if description:
                    desc_lines.append(None)
                continue
            desc_lines.extend(self._wrap(raw, desc_size, False, left_width, italic=True))

        left_height = (
            len(title_lines) * title_line_h + 8 + len(meta_lines) * meta_line_h + 10
            + sum(desc_line_h * 0.6 if l is None else desc_line_h for l in desc_lines)
        )
        block_height = max(left_height, img_h)

        self._ensure_space(block_height)
        top_y = self._y

        y = top_y
        for line in title_lines:
            y -= title_line_h
            self._draw_text(MARGIN, y, line, title_size, family='display', bold=True, color=self.accent)
        y -= 8
        for line in meta_lines:
            y -= meta_line_h
            self._draw_text(MARGIN, y, line, meta_size, family='data', color=MUTED)
        y -= 10
        for line in desc_lines:
            if line is None:
                y -= desc_line_h * 0.6
                continue
            y -= desc_line_h
            self._draw_text(MARGIN, y, line, desc_size, italic=True, color=MUTED)

        if image:
            jpeg_bytes, real_w, real_h = image
            img_x = MARGIN + left_width + gap
            img_y = top_y - img_h
            self._place_image(jpeg_bytes, real_w, real_h, img_x, img_y, img_w, img_h)

        self._y = top_y - block_height - 16

    def ingredient_checklist(self, rows, size=10):
        """Full-width ingredient checklist (for 'consolidated' grouping mode
        - one list for the whole recipe rather than one per step). `rows` is
        a list of (amount_str, food_str, is_header) tuples."""
        content_width = PAGE_WIDTH - 2 * MARGIN
        box = size * 0.75
        amount_col_w = 40
        for amount, _food, is_header in rows:
            if not is_header and amount:
                amount_col_w = max(amount_col_w, self._text_width(amount, size, True, family='data') + 10)
        food_x_offset = box + 8 + amount_col_w
        food_width = content_width - food_x_offset
        row_h = size * 1.6

        for amount, food, is_header in rows:
            if is_header:
                wrapped = self._wrap(food, size, True, content_width, family='data') if food else ['']
                self._ensure_space(row_h * len(wrapped))
                row_top = self._y
                for i, line in enumerate(wrapped):
                    self._draw_text(MARGIN, row_top - i * row_h, line, size, family='data', bold=True, color=MUTED)
                self._y -= row_h * len(wrapped)
                continue
            wrapped = self._wrap(food, size, False, food_width) if food else ['']
            self._ensure_space(row_h * max(1, len(wrapped)))
            row_top = self._y
            self._ops.append(
                f'0.55 0.55 0.55 RG 0.75 w {MARGIN:.2f} {row_top - box - 1:.2f} {box:.2f} {box:.2f} re S'.encode('ascii')
            )
            if amount:
                self._draw_text(MARGIN + box + 6, row_top - size, amount, size, family='data', bold=True, color=self.accent)
            for i, line in enumerate(wrapped):
                self._draw_text(MARGIN + food_x_offset, row_top - size - i * row_h, line, size)
            self._y -= row_h * max(1, len(wrapped))

    def instruction_step(self, index, step_name, instruction, size=10):
        """A step heading followed by its instruction text, full width - no
        ingredient column (for 'consolidated' grouping mode)."""
        label = f'{index}. {step_name}' if step_name else f'Step {index}'
        self._ensure_space(13 * 1.6)
        self._y -= 13
        self._draw_text(MARGIN, self._y, label, 13, family='display', bold=True, color=self.accent)
        self._y -= 13 * 0.4
        self.paragraph(instruction, size=size)
        self._y -= 8

    def step_block(self, index, step_name, ingredients, instruction, size=10, left_frac=0.4, gap=18):
        """A step heading, then two columns underneath it: this step's own
        ingredients as a checklist on the left, its instruction text on the
        right. `ingredients` is a list of (amount_str, food_str, is_header)
        tuples.
        """
        content_width = PAGE_WIDTH - 2 * MARGIN
        left_width = content_width * left_frac
        right_width = content_width - left_width - gap
        right_x = MARGIN + left_width + gap

        heading_size = 12.5

        box = size * 0.75
        # Sized to the longest amount actually in this step rather than a
        # fixed guess - an unexpectedly long amount string would otherwise
        # draw into the food name next to it (this bit the fixed-column
        # version of this layout before).
        amount_col_w = 40
        for amount, _food, is_header in ingredients:
            if not is_header and amount:
                amount_col_w = max(amount_col_w, self._text_width(amount, size, True, family='data') + 10)
        food_x_offset = box + 8 + amount_col_w
        food_width = max(20, left_width - food_x_offset)

        row_h = size * 1.6
        left_rows = []
        for amount, food, is_header in ingredients:
            width = left_width if is_header else food_width
            wrapped = self._wrap(food, size, is_header, width) if food else ['']
            left_rows.append((amount, wrapped, is_header))
        left_height = sum(row_h * max(1, len(w)) for _, w, _ in left_rows)

        line_h = size * 1.35
        right_lines = []
        for raw in (instruction or '').split('\n'):
            if not raw.strip():
                right_lines.append(None)
                continue
            right_lines.extend(self._wrap(raw, size, False, right_width))
        right_height = sum(line_h * 0.6 if l is None else line_h for l in right_lines)

        body_height = max(left_height, right_height)
        total_height = heading_size * 1.3 + 6 + body_height

        self._ensure_space(total_height)

        label = f'{index}. {step_name}' if step_name else f'Step {index}'
        self._y -= heading_size
        self._draw_text(MARGIN, self._y, label, heading_size, family='display', bold=True, color=self.accent)
        self._y -= heading_size * 0.3
        self._y -= 6

        top_y = self._y

        y = top_y
        for amount, wrapped, is_header in left_rows:
            row_top = y
            if is_header:
                for i, line in enumerate(wrapped):
                    self._draw_text(MARGIN, row_top - size - i * row_h, line, size, family='data', bold=True, color=MUTED)
            else:
                self._ops.append(
                    f'0.55 0.55 0.55 RG 0.75 w {MARGIN:.2f} {row_top - box - 1:.2f} {box:.2f} {box:.2f} re S'.encode('ascii')
                )
                if amount:
                    self._draw_text(MARGIN + box + 6, row_top - size, amount, size, family='data', bold=True, color=self.accent)
                for i, line in enumerate(wrapped):
                    self._draw_text(MARGIN + food_x_offset, row_top - size - i * row_h, line, size)
            y -= row_h * max(1, len(wrapped))

        y = top_y
        for line in right_lines:
            if line is None:
                y -= line_h * 0.6
                continue
            y -= line_h
            self._draw_text(right_x, y, line, size)

        self._y = top_y - body_height - 14

    # -- TTF embedding -----------------------------------------------------------
    def _build_tounicode(self, gid_unicode):
        items = sorted(gid_unicode.items())
        chunks = [items[i:i + 90] for i in range(0, len(items), 90)] or [[]]
        body = [
            '/CIDInit /ProcSet findresource begin',
            '12 dict begin',
            'begincmap',
            '/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def',
            '/CMapName /Adobe-Identity-UCS def',
            '/CMapType 2 def',
            '1 begincodespacerange',
            '<0000> <FFFF>',
            'endcodespacerange',
        ]
        for chunk in chunks:
            body.append(f'{len(chunk)} beginbfchar')
            for gid, cp in chunk:
                body.append(f'<{gid:04X}> <{cp:04X}>')
            body.append('endbfchar')
        body += ['endcmap', 'CMapType 1 currentdict /CMap defineresource pop', 'end', 'end']
        stream = '\n'.join(body).encode('ascii')
        return f'<< /Length {len(stream)} >>\nstream\n'.encode('ascii') + stream + b'\nendstream'

    def _build_ttf_font_objects(self, reserve, objects):
        font_ids = {}
        for role in FONT_FILES:
            if not self._used_gids[role]:
                continue  # never drawn - don't pay for embedding it
            font = self._ttf_fonts[role]
            used_gids = sorted(g for g in self._used_gids[role] if g != 0)
            sc = 1000.0 / font.units_per_em

            type0_id = reserve()
            cid_id = reserve()
            descriptor_id = reserve()
            fontfile_id = reserve()

            w_entries = ' '.join(f'{g} [{int(font.advance_for_gid(g) * sc)}]' for g in used_gids)
            objects[cid_id] = (
                f'<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{font.postscript_name} '
                f'/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> '
                f'/FontDescriptor {descriptor_id} 0 R /DW 1000 /W [{w_entries}] '
                f'/CIDToGIDMap /Identity >>'
            ).encode('ascii')

            flags = 5 if role in ('data', 'data_bold') else 4
            bbox = [int(v * sc) for v in font.bbox]
            objects[descriptor_id] = (
                f'<< /Type /FontDescriptor /FontName /{font.postscript_name} /Flags {flags} '
                f'/FontBBox [{bbox[0]} {bbox[1]} {bbox[2]} {bbox[3]}] /ItalicAngle 0 '
                f'/Ascent {int(font.ascent * sc)} /Descent {int(font.descent * sc)} '
                f'/CapHeight 700 /StemV 80 /FontFile2 {fontfile_id} 0 R >>'
            ).encode('ascii')

            compressed = zlib.compress(font.data)
            objects[fontfile_id] = (
                f'<< /Length {len(compressed)} /Length1 {len(font.data)} /Filter /FlateDecode >>\nstream\n'.encode('ascii')
                + compressed + b'\nendstream'
            )

            extra = ''
            if self._gid_unicode[role]:
                tounicode_id = reserve()
                objects[tounicode_id] = self._build_tounicode(self._gid_unicode[role])
                extra = f' /ToUnicode {tounicode_id} 0 R'

            objects[type0_id] = (
                f'<< /Type /Font /Subtype /Type0 /BaseFont /{font.postscript_name} '
                f'/Encoding /Identity-H /DescendantFonts [{cid_id} 0 R]{extra} >>'
            ).encode('ascii')

            font_ids[role] = type0_id
        return font_ids

    # -- serialization ---------------------------------------------------------
    def to_bytes(self):
        self._new_page()
        pages = self._page_contents
        total = len(pages)

        if self.footer_label:
            footer_y = MARGIN - 26
            with_footers = []
            for i, content in enumerate(pages, start=1):
                footer = (
                    _color_op(LIGHT_BORDER, 'RG')
                    + f' 0.75 w {MARGIN:.2f} {footer_y + 12:.2f} m {PAGE_WIDTH - MARGIN:.2f} {footer_y + 12:.2f} l S'.encode('ascii')
                )
                footer += b'\n' + self._text_bytes(MARGIN, footer_y, self.footer_label, 8, family='data', color=MUTED)
                page_label = f'Page {i} of {total}'
                label_w = self._text_width(page_label, 8, family='data')
                footer += b'\n' + self._text_bytes(
                    PAGE_WIDTH - MARGIN - label_w, footer_y, page_label, 8, family='data', color=MUTED
                )
                with_footers.append(content + b'\n' + footer)
            pages = with_footers

        objects = {}
        next_id = [1]

        def reserve():
            oid = next_id[0]
            next_id[0] += 1
            return oid

        catalog_id = reserve()
        pages_id = reserve()

        if self.use_ttf:
            font_ids = self._build_ttf_font_objects(reserve, objects)
            font_entries = ' '.join(f'/{ROLE_PDF_NAMES[role]} {oid} 0 R' for role, oid in font_ids.items())
        else:
            font1_id, font2_id, font3_id = reserve(), reserve(), reserve()
            regular, bold, italic = FONT_FAMILIES[self.font_family]
            objects[font1_id] = f'<< /Type /Font /Subtype /Type1 /BaseFont /{regular} /Encoding /WinAnsiEncoding >>'.encode('ascii')
            objects[font2_id] = f'<< /Type /Font /Subtype /Type1 /BaseFont /{bold} /Encoding /WinAnsiEncoding >>'.encode('ascii')
            objects[font3_id] = f'<< /Type /Font /Subtype /Type1 /BaseFont /{italic} /Encoding /WinAnsiEncoding >>'.encode('ascii')
            font_entries = f'/F1 {font1_id} 0 R /F2 {font2_id} 0 R /F3 {font3_id} 0 R'

        image_ids = [reserve() for _ in self._images]
        page_ids = [reserve() for _ in pages]
        content_ids = [reserve() for _ in pages]
        resources_id = reserve()

        for oid, (jpeg_bytes, width, height) in zip(image_ids, self._images):
            header = (
                f'<< /Type /XObject /Subtype /Image /Width {width} /Height {height} '
                f'/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode '
                f'/Length {len(jpeg_bytes)} >>\nstream\n'
            ).encode('ascii')
            objects[oid] = header + jpeg_bytes + b'\nendstream'

        xobject_entries = ' '.join(f'/Im{i} {oid} 0 R' for i, oid in enumerate(image_ids))
        objects[resources_id] = (
            f'<< /Font << {font_entries} >> /XObject << {xobject_entries} >> >>'
        ).encode('ascii')

        for page_id, content_id, content in zip(page_ids, content_ids, pages):
            stream_body = f'<< /Length {len(content)} >>\nstream\n'.encode('ascii') + content + b'\nendstream'
            objects[content_id] = stream_body
            objects[page_id] = (
                f'<< /Type /Page /Parent {pages_id} 0 R '
                f'/MediaBox [0 0 {PAGE_WIDTH:.2f} {PAGE_HEIGHT:.2f}] '
                f'/Resources {resources_id} 0 R /Contents {content_id} 0 R >>'
            ).encode('ascii')

        kids = ' '.join(f'{pid} 0 R' for pid in page_ids)
        objects[pages_id] = f'<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>'.encode('ascii')
        objects[catalog_id] = f'<< /Type /Catalog /Pages {pages_id} 0 R >>'.encode('ascii')

        buf = bytearray()
        buf += b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n'
        offsets = {}
        for oid in sorted(objects):
            offsets[oid] = len(buf)
            buf += f'{oid} 0 obj\n'.encode('ascii')
            body = objects[oid]
            buf += body
            if not body.endswith(b'\n'):
                buf += b'\n'
            buf += b'endobj\n'

        xref_offset = len(buf)
        count = max(objects) + 1
        buf += f'xref\n0 {count}\n'.encode('ascii')
        buf += b'0000000000 65535 f \n'
        for oid in range(1, count):
            buf += f'{offsets.get(oid, 0):010d} 00000 n \n'.encode('ascii')
        buf += b'trailer\n'
        buf += f'<< /Size {count} /Root {catalog_id} 0 R >>\n'.encode('ascii')
        buf += b'startxref\n'
        buf += f'{xref_offset}\n'.encode('ascii')
        buf += b'%%EOF'
        return bytes(buf)
