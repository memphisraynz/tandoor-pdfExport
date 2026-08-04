# Tandoor PDF Export Plugin

Adds a "Export Recipe to PDF" page to Tandoor (linked from the user menu),
where you can search for a recipe and download it as a nicely formatted PDF.

Uses [WeasyPrint](https://weasyprint.org/) for PDF rendering, since Tandoor
removed its own (pyppeteer-based) PDF export in v1 and now only supports
"print to PDF via the browser".

## How Tandoor plugins work (short version)

There's no package registry - plugins are git repos cloned directly into
`recipes/plugins/<name>/` inside a Tandoor install. On boot, Tandoor scans
that directory and auto-registers anything with an `apps.py`. See
`apps.py`/`urls.py`/`setup_repo.py` in this repo for how the pieces fit
together; the code comments explain the non-obvious parts (e.g. why
`pdf_export_router` exists even though it's empty).

## Installation

1. Clone this repo into your Tandoor install's `recipes/plugins/` directory,
   as `pdf_export_plugin`:

   ```bash
   # bare metal / dev checkout
   git clone <this-repo-url> recipes/plugins/pdf_export_plugin

   # docker: mount recipes/plugins as a volume on the host, then clone into it
   git clone <this-repo-url> /path/to/host/mounted/recipes/plugins/pdf_export_plugin
   ```

2. Install WeasyPrint (not bundled with Tandoor) **inside the container/venv
   Tandoor runs in**, plus its native dependencies (Pango, Cairo, GDK-Pixbuf -
   pure `pip install` alone is not enough). Easiest way is a small wrapper
   Dockerfile on top of whatever Tandoor image you currently use:

   ```dockerfile
   FROM <your-current-tandoor-image>:<tag>

   # Adjust the package manager/names if your base image isn't Alpine.
   RUN apk add --no-cache pango cairo gdk-pixbuf ttf-freefont font-noto \
       && pip install --no-cache-dir -r /app/recipes/plugins/pdf_export_plugin/requirements-plugin.txt
   ```

   Point your `docker-compose.yml` at this image instead of the stock one.

3. Set `PLUGINS_BUILD=1` in Tandoor's environment so the frontend gets
   rebuilt with this plugin's Vue page included. Note: this reruns
   `yarn install && yarn build` for the *entire* frontend on every restart,
   so it's slow - once you're happy with the plugin, you can drop the env
   var again and bake the build into your custom image instead.

4. Restart Tandoor. On the admin "System" page you should see "PDF Export"
   listed under Plugins, and a new "Export Recipe to PDF" entry in the user
   menu (top-right avatar dropdown).

## Known limitations

- There's no supported way to add a button directly to the recipe's own
  "3 dot" action menu (Edit/Add to Shopping/Print/...) - that menu is a
  hardcoded template in Tandoor core with no plugin extension point. This
  plugin instead ships its own page where you pick the recipe to export.
- No automated tests / CI yet - this is a first pass, verify PDF output
  against a couple of real recipes (with/without image, with/without
  nutrition info, with ingredient group headers) before relying on it.
