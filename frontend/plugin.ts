import {TandoorPlugin} from '@/types/Plugins.ts'
import {VListItem} from "vuetify/components";

export const plugin: TandoorPlugin = {
    name: 'PDF Export',
    basePath: 'pdf_export_plugin',
    defaultLocale: import(`@/plugins/pdf_export_plugin/locales/en.json`),
    localeFiles: import.meta.glob('@/plugins/pdf_export_plugin/locales/*.json'),
    routes: [
        {path: '/pdf-export/', component: () => import("@/plugins/pdf_export_plugin/pages/PdfExportPage.vue"), name: 'PdfExportPage'},
    ],
    navigationDrawer: [],
    bottomNavigation: [],
    userNavigation: [
        {component: VListItem, prependIcon: 'fa-solid fa-file-pdf', title: 'Export_Recipe_PDF', to: {name: 'PdfExportPage', params: {}}},
    ],
    disabled: false,
} as TandoorPlugin
