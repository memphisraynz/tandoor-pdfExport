import {TandoorPlugin} from '@/types/Plugins.ts'
import SettingsNavItem from "@/plugins/tandoor-pdfExport/components/SettingsNavItem.vue";

export const plugin: TandoorPlugin = {
    name: 'PDF Export',
    basePath: 'tandoor-pdfExport',
    defaultLocale: import(`@/plugins/tandoor-pdfExport/locales/en.json`),
    localeFiles: import.meta.glob('@/plugins/tandoor-pdfExport/locales/*.json'),
    routes: [],
    // Registers the page under /settings/... - on its own this makes the
    // page reachable by URL but adds no visible tab (SettingsPage.vue's
    // tab list is a separate, hardcoded-for-built-ins mechanism). The
    // settingsComponent below is what actually renders the clickable tab.
    settingRoutes: [
        {path: 'pdf-export', component: () => import("@/plugins/tandoor-pdfExport/pages/PdfExportPage.vue"), name: 'SettingsPdfExport'},
    ],
    navigationDrawer: [],
    bottomNavigation: [],
    userNavigation: [],
    settingsComponent: SettingsNavItem,
    disabled: false,
} as TandoorPlugin
