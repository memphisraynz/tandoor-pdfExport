"""Minimal pure-stdlib TrueType font parser.

Extracts exactly what's needed to embed a TTF in a PDF as a Type0/
Identity-H CID font: unitsPerEm, ascent/descent/bbox, per-glyph advance
widths (hmtx), a Unicode-to-glyph-ID lookup (cmap format 4), and the
font's PostScript name (for a sensible /BaseFont). No dependency beyond
the `struct` module from the standard library - this intentionally
doesn't parse glyph outlines, hinting, variable-font axes, or anything
else; it only reads the handful of tables needed for correct text
layout and embedding.
"""

import struct


class TTFFont:
    def __init__(self, path):
        with open(path, 'rb') as f:
            self.data = f.read()
        self._tables = self._read_table_directory()
        self.units_per_em = self._read_units_per_em()
        self.ascent, self.descent = self._read_hhea()
        self.bbox = self._read_bbox()
        self._num_h_metrics = self._read_num_h_metrics()
        self._gid_cache = {}
        self._advance_cache = {}
        self._cmap_lookup = self._build_cmap()
        self.postscript_name = self._read_postscript_name(path)

    def _read_table_directory(self):
        d = self.data
        num_tables = struct.unpack('>H', d[4:6])[0]
        tables = {}
        for i in range(num_tables):
            o = 12 + i * 16
            tag = d[o:o + 4].decode('latin-1')
            offset, length = struct.unpack('>II', d[o + 8:o + 16])
            tables[tag] = (offset, length)
        return tables

    def _read_units_per_em(self):
        off, _ = self._tables['head']
        return struct.unpack('>H', self.data[off + 18:off + 20])[0]

    def _read_hhea(self):
        off, _ = self._tables['hhea']
        return struct.unpack('>hh', self.data[off + 4:off + 8])

    def _read_bbox(self):
        off, _ = self._tables['head']
        return struct.unpack('>hhhh', self.data[off + 36:off + 44])

    def _read_num_h_metrics(self):
        off, _ = self._tables['hhea']
        return struct.unpack('>H', self.data[off + 34:off + 36])[0]

    def _build_cmap(self):
        d = self.data
        co, _ = self._tables['cmap']
        n = struct.unpack('>H', d[co + 2:co + 4])[0]
        found = {}
        for i in range(n):
            p = co + 4 + i * 8
            platform_id, encoding_id, offset = struct.unpack('>HHI', d[p:p + 8])
            found[(platform_id, encoding_id)] = co + offset
        # Prefer a full Unicode BMP subtable; these are the platform/encoding
        # pairs that are actually format 4 in practice for our font set.
        sub_offset = None
        for key in [(3, 1), (0, 3), (3, 10), (0, 4), (0, 6)]:
            if key in found:
                sub_offset = found[key]
                break
        if sub_offset is None and found:
            sub_offset = next(iter(found.values()))
        if sub_offset is None:
            raise ValueError(f'{self} has no usable cmap subtable')

        fmt = struct.unpack('>H', d[sub_offset:sub_offset + 2])[0]
        if fmt != 4:
            raise ValueError(f'unsupported cmap format {fmt} (only format 4 is supported)')

        seg_x2 = struct.unpack('>H', d[sub_offset + 6:sub_offset + 8])[0]
        seg_count = seg_x2 // 2
        ends = struct.unpack(f'>{seg_count}H', d[sub_offset + 14:sub_offset + 14 + seg_x2])
        starts_off = sub_offset + 16 + seg_x2
        starts = struct.unpack(f'>{seg_count}H', d[starts_off:starts_off + seg_x2])
        deltas_off = starts_off + seg_x2
        deltas = struct.unpack(f'>{seg_count}h', d[deltas_off:deltas_off + seg_x2])
        range_off_off = deltas_off + seg_x2
        range_offsets = struct.unpack(f'>{seg_count}H', d[range_off_off:range_off_off + seg_x2])

        def lookup(codepoint):
            for i in range(seg_count):
                if codepoint <= ends[i]:
                    if codepoint < starts[i]:
                        return 0
                    if range_offsets[i] == 0:
                        return (codepoint + deltas[i]) & 0xFFFF
                    glyph_addr = (range_off_off + i * 2 + range_offsets[i]
                                  + (codepoint - starts[i]) * 2)
                    if glyph_addr + 2 > len(d):
                        return 0
                    gid = struct.unpack('>H', d[glyph_addr:glyph_addr + 2])[0]
                    return 0 if gid == 0 else (gid + deltas[i]) & 0xFFFF
            return 0

        return lookup

    def _read_postscript_name(self, path):
        try:
            off, _ = self._tables['name']
            d = self.data
            count = struct.unpack('>H', d[off + 2:off + 4])[0]
            storage_off = off + struct.unpack('>H', d[off + 4:off + 6])[0]
            best = None
            for i in range(count):
                r = off + 6 + i * 12
                platform_id, encoding_id, _lang, name_id, length, rec_off = struct.unpack(
                    '>HHHHHH', d[r:r + 12]
                )
                if name_id != 6:
                    continue
                raw = d[storage_off + rec_off:storage_off + rec_off + length]
                if platform_id == 3:
                    text = raw.decode('utf-16-be', errors='ignore')
                    best = text
                    break
                if best is None:
                    best = raw.decode('latin-1', errors='ignore')
            if best:
                return ''.join(c for c in best if c.isalnum() or c in '-_')
        except Exception:
            pass
        import os
        return os.path.splitext(os.path.basename(path))[0]

    def gid_for_char(self, ch):
        cp = ord(ch)
        gid = self._gid_cache.get(cp)
        if gid is None:
            gid = self._cmap_lookup(cp)
            self._gid_cache[cp] = gid
        return gid

    def advance_for_gid(self, gid):
        advance = self._advance_cache.get(gid)
        if advance is not None:
            return advance
        off, _ = self._tables['hmtx']
        if gid < self._num_h_metrics:
            advance = struct.unpack('>H', self.data[off + gid * 4:off + gid * 4 + 2])[0]
        else:
            last = max(self._num_h_metrics - 1, 0)
            advance = struct.unpack('>H', self.data[off + last * 4:off + last * 4 + 2])[0]
        self._advance_cache[gid] = advance
        return advance

    def text_width(self, text, size):
        total = 0
        for ch in text:
            total += self.advance_for_gid(self.gid_for_char(ch))
        return total * size / self.units_per_em
