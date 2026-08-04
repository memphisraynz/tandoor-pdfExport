# Tandoor PDF Export Plugin

Adds a "PDF Export" entry both under Settings and in the user avatar
menu, where you can search for a recipe, download it as a formatted PDF,
and customize the font/accent color/image style used. Also reachable
directly at `/pdf-export/` (a plain server-rendered page, no Vue/JS
build involved) as a fallback that doesn't depend on the frontend build
succeeding.

The PDF itself: an auto-fitting title (shrinks to fit rather than
overflowing) with description on the left, the recipe photo on the right
(cropped to a fixed box by default, so a full-resolution portrait or
landscape photo doesn't distort or letterbox oddly - or choose "Full
image" in the appearance settings to fit it uncropped instead), then a
labeled spec band (Servings / Prep / Bake, whichever the recipe has).
Section labels (Ingredients/Instructions/Nutrition) are small,
letterspaced, uppercase, with a rule in a tint of the accent color
underneath; each step gets a large accent-colored numeral next to a
letterspaced label and a rule out to the page edge. Each step shows its
own ingredient checklist next to its own instructions by default, rather
than one big ingredients list followed by one big instructions list -
switchable in appearance settings ("Ingredient Grouping").

It's under Settings rather than the existing recipe Import/Export
section because that section is a hardcoded core mechanism (a fixed
if/elif chain of built-in "Integration" classes) with no plugin
extension point at all - same limitation as the recipe's own "3 dot"
menu below.

PDF generation (`pdf_writer.py` + `ttf_font.py`) is hand-rolled directly
against the PDF file format using only the Python standard library, plus
Pillow for image conversion - which Tandoor already ships. There is
nothing to install: no pip package, no system library (no Pango/Cairo/
etc.), no custom Docker image. `git pull` + restart is the entire
deployment step.

This is a deliberate trade-off over using a real PDF library (WeasyPrint,
xhtml2pdf, etc.): those all either need native system libraries or a
third-party pip package installed inside the container, which doesn't
survive a plain restart/recreate without a custom image.

### Fonts

Default rendering mode ("Serif" in appearance settings) embeds four real
TrueType fonts - Gloock (titles/step numerals), Lora (body prose, regular/
italic/bold), and IBM Plex Mono (quantities, labels, footer) - as proper
`Type0`/`Identity-H` CID fonts, parsed and embedded with nothing but
`struct` from the standard library (`ttf_font.py`; no font-parsing
library either). This means genuinely accurate word-wrap (real glyph
metrics, not an approximation) and a much wider character repertoire
than a moment ago - Cyrillic, fraction glyphs, most of Latin Extended -
with searchable/copyable text via an embedded `/ToUnicode` CMap. All
four font files live in `fonts/` under the SIL Open Font License
(license text alongside each, `fonts/OFL-*.txt`); only fonts actually
used by a given recipe get embedded, so a recipe with no italic text
doesn't pay for `Lora-Italic.ttf`. A typical recipe with one photo runs
roughly 300-400 KB. If the font files are ever missing or fail to parse
for any reason, this falls back automatically to the standard-14 option
below rather than failing the export.

The three other font choices (Helvetica, Times, Courier) are the
original standard-14 PDF fonts - no embedding, much smaller files,
WinAnsiEncoding (~cp1252) only so non-Latin-1 text (CJK, Cyrillic)
renders as "?", and word-wrap is an approximation rather than real
metrics. Useful if file size matters more than typography to you.

## Appearance settings

Stored per-user in a small `PdfExportSettings` model (this plugin's only
database table): font (serif/helvetica/times/courier), accent color
(hex), image style (cropped/full), ingredient grouping (grouped by step
vs. one combined list), and note prefix (none/"Note:"/"NB:" - an
ingredient's note is always shown on its own smaller, muted, italic line
under the ingredient rather than inline in parentheses; this only
controls whether it's prefixed). The settings form in the Vue page talks to
a plain JSON endpoint at `/pdf-export/api/settings/` (GET to read, POST
to save) - this is hand-written, not part of Tandoor's generated API
client (which has no knowledge of plugin endpoints), so it's the one
part of this plugin I haven't been able to verify end-to-end myself. If
saving preferences doesn't work, check the browser console for a
CSRF-related error first - the POST manually attaches Django's
`csrftoken` cookie value as an `X-CSRFToken` header, which assumes
Tandoor hasn't renamed that cookie from Django's default.

## How Tandoor plugins work (short version)

There's no package registry - plugins are git repos cloned directly into
`recipes/plugins/<name>/` inside a Tandoor install. On boot, Tandoor scans
that directory and auto-registers anything with an `apps.py`. See
`apps.py`/`urls.py`/`setup_repo.py` in this repo for how the pieces fit
together; the code comments explain the non-obvious parts (e.g. why
`pdf_export_router` exists even though it's empty, and why `apps.py`
resolves its Django app name from `__package__` instead of a hardcoded
string - so it works no matter what you name the folder you clone into).

## Installation

1. Clone this repo into your Tandoor install's `recipes/plugins/` directory
   (Docker: wherever that's volume-mounted to on the host):

   ```bash
   git clone https://github.com/memphisraynz/tandoor-pdfExport.git recipes/plugins/tandoor-pdfExport
   ```

2. Set `PLUGINS_BUILD=1` in Tandoor's environment so the frontend gets
   rebuilt with this plugin's Vue page included. Note: this reruns
   `yarn install && yarn build` for the *entire* frontend on every restart,
   so it's slow - once you're happy with the plugin, you can drop the env
   var again so future restarts skip it.

3. Restart Tandoor. On the admin "System" page you should see "PDF Export"
   listed under Plugins, and a new "PDF Export" tab under Settings (and
   in the user avatar menu). The plugin's database migrations run
   automatically as part of Tandoor's normal `manage.py migrate` on boot
   - no separate migration step needed.

That's it - no other setup step, on the server or anywhere else.

## Known limitations

- There's no supported way to add a button directly to the recipe's own
  "3 dot" action menu (Edit/Add to Shopping/Print/...) - that menu is a
  hardcoded template in Tandoor core with no plugin extension point. This
  plugin instead ships its own page where you pick the recipe to export.
- No automated tests / CI yet - this is a first pass, verify PDF output
  against a couple of real recipes (with/without image, with/without
  nutrition info, with ingredient group headers) before relying on it.
- In "Serif" mode, a character missing from the relevant font (e.g. a
  script none of Gloock/Lora/IBM Plex Mono cover) renders as blank rather
  than "?" or a tofu box - silent, not a crash, but worth knowing if a
  recipe name uses an unusual script.
