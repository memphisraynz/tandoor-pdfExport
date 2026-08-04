"""Minimal, dependency-free PDF writer.

Generates a simple single-column document (headings, wrapped paragraphs,
two-column rows, one embedded JPEG image) directly as PDF bytes, using
only the Python standard library - no third-party PDF package and no
system library (Pango/Cairo/etc.) needs to be installed anywhere.

This is intentionally NOT a general-purpose PDF library - standard 14
fonts only (Helvetica/Helvetica-Bold) with WinAnsiEncoding (~cp1252);
characters outside that range are replaced with '?'. Word-wrap widths
are an approximation (Helvetica isn't monospace and we don't carry a
real glyph-width table), so occasionally a line may look a little
looser/tighter than a real typesetting engine would produce - that's a
cosmetic trade-off for having zero external dependencies, not a bug.

Good enough for a one-page recipe printout; nothing more is in scope.
"""

PAGE_WIDTH = 595.28   # A4, in points (1/72 inch)
PAGE_HEIGHT = 841.89
MARGIN = 56.7         # ~2cm

_NARROW = set('iIl.,;:\'"|!fjt ')
_WIDE = set('mwMW@%')


def _char_width(ch, size, bold):
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


def _text_width(text, size, bold):
    return sum(_char_width(c, size, bold) for c in text)


def text_width(text, size, bold=False):
    """Public wrapper so callers can size layout (e.g. a table column) to
    fit a specific piece of text before drawing it."""
    return _text_width(text, size, bold)


def _wrap(text, size, bold, max_width):
    """Word-wrap a single line (no embedded newlines) to fit max_width."""
    lines = []
    current = ''
    for word in text.split(' '):
        candidate = f'{current} {word}'.strip()
        if current and _text_width(candidate, size, bold) > max_width:
            lines.append(current)
            current = word
        else:
            current = candidate
        # Hard-break a single word/fragment that's wider than a whole line.
        while _text_width(current, size, bold) > max_width and len(current) > 1:
            lo, hi = 1, len(current)
            while lo < hi:
                mid = (lo + hi + 1) // 2
                if _text_width(current[:mid], size, bold) <= max_width:
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


class PDFDocument:
    def __init__(self):
        self._page_contents = []   # list of bytes, one per completed page
        self._images = []          # list of (jpeg_bytes, width, height)
        self._ops = []             # list of bytes, current page's operators
        self._y = PAGE_HEIGHT - MARGIN

    # -- low level ---------------------------------------------------------
    def _new_page(self):
        self._page_contents.append(b'\n'.join(self._ops))
        self._ops = []
        self._y = PAGE_HEIGHT - MARGIN

    def _ensure_space(self, height):
        if self._y - height < MARGIN:
            self._new_page()

    def _draw_text(self, x, y, text, size, bold):
        font = b'/F2' if bold else b'/F1'
        op = (
            b'BT ' + font + f' {size:.1f} Tf {x:.2f} {y:.2f} Td ('.encode('ascii')
            + _pdf_text_bytes(text) + b') Tj ET'
        )
        self._ops.append(op)

    # -- public layout API ---------------------------------------------------
    def heading(self, text, size=15):
        self._ensure_space(size * 1.6)
        self._y -= size
        self._draw_text(MARGIN, self._y, text, size, bold=True)
        self._y -= size * 0.6

    def paragraph(self, text, size=10, bold=False):
        max_width = PAGE_WIDTH - 2 * MARGIN
        line_height = size * 1.35
        for raw_line in (text or '').split('\n'):
            if not raw_line.strip():
                self._y -= line_height * 0.6
                continue
            for line in _wrap(raw_line, size, bold, max_width):
                self._ensure_space(line_height)
                self._y -= line_height
                self._draw_text(MARGIN, self._y, line, size, bold)

    def two_column_line(self, left, right, size=10, indent=0, col_width=95):
        max_width = PAGE_WIDTH - 2 * MARGIN - indent - col_width
        line_height = size * 1.4
        for i, line in enumerate(_wrap(right, size, False, max_width)):
            self._ensure_space(line_height)
            self._y -= line_height
            if i == 0 and left:
                self._draw_text(MARGIN + indent, self._y, left, size, bold=True)
            self._draw_text(MARGIN + indent + col_width, self._y, line, size, bold=False)

    def rule(self):
        self._ensure_space(4)
        self._y -= 4
        self._ops.append(
            f'{MARGIN:.2f} {self._y:.2f} m {PAGE_WIDTH - MARGIN:.2f} {self._y:.2f} l S'.encode('ascii')
        )
        self._y -= 8

    def image(self, jpeg_bytes, width, height, max_width=240, max_height=200):
        scale = min(max_width / width, max_height / height, 1)
        w, h = width * scale, height * scale
        self._ensure_space(h + 10)
        self._y -= h
        idx = len(self._images)
        self._images.append((jpeg_bytes, width, height))
        self._ops.append(
            f'q {w:.2f} 0 0 {h:.2f} {MARGIN:.2f} {self._y:.2f} cm /Im{idx} Do Q'.encode('ascii')
        )
        self._y -= 10

    # -- serialization -------------------------------------------------------
    def to_bytes(self):
        self._new_page()
        pages = self._page_contents

        objects = {}
        next_id = [1]

        def reserve():
            oid = next_id[0]
            next_id[0] += 1
            return oid

        catalog_id = reserve()
        pages_id = reserve()
        font1_id = reserve()
        font2_id = reserve()
        image_ids = [reserve() for _ in self._images]
        page_ids = [reserve() for _ in pages]
        content_ids = [reserve() for _ in pages]
        resources_id = reserve()

        objects[font1_id] = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>'
        objects[font2_id] = b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>'

        for oid, (jpeg_bytes, width, height) in zip(image_ids, self._images):
            header = (
                f'<< /Type /XObject /Subtype /Image /Width {width} /Height {height} '
                f'/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode '
                f'/Length {len(jpeg_bytes)} >>\nstream\n'
            ).encode('ascii')
            objects[oid] = header + jpeg_bytes + b'\nendstream'

        xobject_entries = ' '.join(f'/Im{i} {oid} 0 R' for i, oid in enumerate(image_ids))
        objects[resources_id] = (
            f'<< /Font << /F1 {font1_id} 0 R /F2 {font2_id} 0 R >> '
            f'/XObject << {xobject_entries} >> >>'
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
