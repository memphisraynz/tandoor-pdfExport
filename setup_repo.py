import os

PLUGIN_NAME = 'tandoor-pdfExport'

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# CURRENT_DIR = <tandoor>/recipes/plugins/tandoor-pdfExport, so three levels
# up is the Tandoor repo root (the same directory that contains vue3/).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))

VUE_PLUGINS_DIR = os.path.join(BASE_DIR, 'vue3', 'src', 'plugins')
PLUGIN_FRONTEND_DIR = os.path.join(CURRENT_DIR, 'frontend')

# Clean up any symlink left over from this plugin being linked under a
# different PLUGIN_NAME in the past (e.g. before a rename) - otherwise
# Vite's `import.meta.glob('@/plugins/*/plugin.ts')` finds the same
# plugin.ts under two different folder names and registers it twice
# (visible as duplicate nav items/tabs).
if os.path.isdir(VUE_PLUGINS_DIR):
    frontend_real = os.path.realpath(PLUGIN_FRONTEND_DIR)
    for entry in os.listdir(VUE_PLUGINS_DIR):
        if entry == PLUGIN_NAME:
            continue
        entry_path = os.path.join(VUE_PLUGINS_DIR, entry)
        if os.path.islink(entry_path) and os.path.realpath(entry_path) == frontend_real:
            os.remove(entry_path)
            print(f'Removed stale symlink {entry_path} (pointed at this plugin under an old name)')

target = os.path.join(VUE_PLUGINS_DIR, PLUGIN_NAME)

if not os.path.exists(target):
    os.makedirs(VUE_PLUGINS_DIR, exist_ok=True)
    os.symlink(PLUGIN_FRONTEND_DIR, target)
    print(f'Linked {PLUGIN_FRONTEND_DIR} -> {target}')
else:
    print(f'{target} already exists, skipping symlink')
