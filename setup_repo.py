import os

PLUGIN_NAME = 'tandoor-pdfExport'

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
# CURRENT_DIR = <tandoor>/recipes/plugins/tandoor-pdfExport, so three levels
# up is the Tandoor repo root (the same directory that contains vue3/).
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(CURRENT_DIR)))

VUE_PLUGINS_DIR = os.path.join(BASE_DIR, 'vue3', 'src', 'plugins')
PLUGIN_FRONTEND_DIR = os.path.join(CURRENT_DIR, 'frontend')

target = os.path.join(VUE_PLUGINS_DIR, PLUGIN_NAME)

if not os.path.exists(target):
    os.makedirs(VUE_PLUGINS_DIR, exist_ok=True)
    os.symlink(PLUGIN_FRONTEND_DIR, target)
    print(f'Linked {PLUGIN_FRONTEND_DIR} -> {target}')
else:
    print(f'{target} already exists, skipping symlink')
