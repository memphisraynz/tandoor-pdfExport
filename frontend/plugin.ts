import {TandoorPlugin} from '@/types/Plugins.ts'
import {VListItem} from "vuetify/components";
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
    // Same page, reachable from both places - a named route can be linked
    // to from anywhere regardless of where it's nested in the route tree.
    userNavigation: [
        {component: VListItem, prependIcon: 'fa-solid fa-file-pdf', title: 'Export_Recipe_PDF', to: {name: 'SettingsPdfExport'}},
    ],
    settingsComponent: SettingsNavItem,
    disabled: false,
} as TandoorPlugin
