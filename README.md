# Tandoor PDF Export Plugin

Adds a "PDF Export" tab under Settings, where you can search for a recipe
and download it as a formatted PDF. Also reachable directly at
`/pdf-export/` (a plain server-rendered page, no Vue/JS build involved)
as a fallback that doesn't depend on the frontend build succeeding.

It's under Settings rather than the existing recipe Import/Export
section because that section is a hardcoded core mechanism (a fixed
if/elif chain of built-in "Integration" classes) with no plugin
extension point at all - same limitation as the recipe's own "3 dot"
menu below.

PDF generation (`pdf_writer.py`) is hand-rolled directly against the PDF
file format using only the Python standard library, plus Pillow for
image conversion - which Tandoor already ships. There is nothing to
install: no pip package, no system library (no Pango/Cairo/etc.), no
custom Docker image. `git pull` + restart is the entire deployment step.

This is a deliberate trade-off over using a real PDF library (WeasyPrint,
xhtml2pdf, etc.): those all either need native system libraries or a
third-party pip package installed inside the container, which doesn't
survive a plain restart/recreate without a custom image. Word-wrapping
uses an approximate per-character width table rather than real font
metrics, so line breaks are close-enough rather than typographically
perfect - a cosmetic trade-off, not a correctness one. Text outside
Latin-1/WinAnsiEncoding (e.g. CJK or Cyrillic recipe names) will render
as "?", since embedding real Unicode fonts is out of scope for this.

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
   listed under Plugins, and a new "PDF Export" tab under Settings.

That's it - no other setup step, on the server or anywhere else.

## Known limitations

- There's no supported way to add a button directly to the recipe's own
  "3 dot" action menu (Edit/Add to Shopping/Print/...) - that menu is a
  hardcoded template in Tandoor core with no plugin extension point. This
  plugin instead ships its own page where you pick the recipe to export.
- No automated tests / CI yet - this is a first pass, verify PDF output
  against a couple of real recipes (with/without image, with/without
  nutrition info, with ingredient group headers) before relying on it.
