import {TandoorPlugin} from '@/types/Plugins.ts'
import {VListItem} from "vuetify/components";

export const plugin: TandoorPlugin = {
    name: 'PDF Export',
    basePath: 'tandoor-pdfExport',
    defaultLocale: import(`@/plugins/tandoor-pdfExport/locales/en.json`),
    localeFiles: import.meta.glob('@/plugins/tandoor-pdfExport/locales/*.json'),
    routes: [
        {path: '/pdf-export/', component: () => import("@/plugins/tandoor-pdfExport/pages/PdfExportPage.vue"), name: 'PdfExportPage'},
    ],
    navigationDrawer: [],
    bottomNavigation: [],
    userNavigation: [
        {component: VListItem, prependIcon: 'fa-solid fa-file-pdf', title: 'Export_Recipe_PDF', to: {name: 'PdfExportPage', params: {}}},
    ],
    disabled: false,
} as TandoorPlugin
