<template>
    <v-container>
        <v-row>
            <v-col cols="12" lg="9" xl="7">
                <h1 class="mb-4">{{ $t('Export_Recipe_PDF') }}</h1>
                <p class="text-medium-emphasis mb-4">{{ $t('Export_Recipe_PDF_Help') }}</p>

                <ModelSelect model="Recipe" v-model="selectedRecipe" :label="$t('Recipe')"/>

                <v-btn
                    class="mt-4 mb-8"
                    color="primary"
                    :disabled="!selectedRecipe"
                    prepend-icon="fa-solid fa-file-pdf"
                    :href="downloadUrl"
                    target="_blank"
                >
                    {{ $t('Download_PDF') }}
                </v-btn>

                <v-divider class="mb-6"></v-divider>

                <h2 class="text-h6 mb-4">{{ $t('PDF_Appearance') }}</h2>

                <v-select
                    v-model="prefs.font"
                    :items="fontChoices"
                    :label="$t('Font')"
                    class="mb-2"
                ></v-select>

                <v-text-field
                    v-model="prefs.accent_color"
                    type="color"
                    :label="$t('Accent_Color')"
                    class="mb-2"
                    style="max-width: 160px;"
                ></v-text-field>

                <v-select
                    v-model="prefs.image_style"
                    :items="imageStyleChoices"
                    :label="$t('Image_Style')"
                    class="mb-2"
                ></v-select>

                <v-select
                    v-model="prefs.ingredient_grouping"
                    :items="ingredientGroupingChoices"
                    :label="$t('Ingredient_Grouping')"
                    class="mb-2"
                ></v-select>

                <v-select
                    v-model="prefs.note_style"
                    :items="noteStyleChoices"
                    :label="$t('Note_Prefix')"
                    class="mb-4"
                ></v-select>

                <v-btn color="primary" variant="tonal" :loading="saving" @click="savePreferences">
                    {{ $t('Save') }}
                </v-btn>
                <span v-if="saved" class="text-success ml-3">{{ $t('Saved') }}</span>
            </v-col>
        </v-row>
    </v-container>
</template>

<script setup lang="ts">
import {computed, onMounted, ref} from 'vue'
import ModelSelect from '@/components/inputs/ModelSelect.vue'

const selectedRecipe = ref<any>(null)

const downloadUrl = computed(() => {
    if (!selectedRecipe.value) {
        return undefined
    }
    return `/pdf-export/recipe/${selectedRecipe.value.id}/pdf/`
})

const prefs = ref({
    font: 'serif',
    accent_color: '#b85c1a',
    image_style: 'cropped',
    ingredient_grouping: 'per_step',
    note_style: 'none',
})
const fontChoices = ref<{ title: string, value: string }[]>([])
const imageStyleChoices = ref<{ title: string, value: string }[]>([])
const ingredientGroupingChoices = ref<{ title: string, value: string }[]>([])
const noteStyleChoices = ref<{ title: string, value: string }[]>([])
const saving = ref(false)
const saved = ref(false)

function getCookie(name: string): string {
    const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
    return match ? decodeURIComponent(match[2]) : ''
}

function toItems(choices: [string, string][]) {
    return choices.map(([value, title]) => ({value, title}))
}

async function loadPreferences() {
    const res = await fetch('/pdf-export/api/settings/', {credentials: 'same-origin'})
    if (!res.ok) {
        return
    }
    const data = await res.json()
    prefs.value = {
        font: data.font,
        accent_color: data.accent_color,
        image_style: data.image_style,
        ingredient_grouping: data.ingredient_grouping,
        note_style: data.note_style,
    }
    fontChoices.value = toItems(data.font_choices)
    imageStyleChoices.value = toItems(data.image_style_choices)
    ingredientGroupingChoices.value = toItems(data.ingredient_grouping_choices)
    noteStyleChoices.value = toItems(data.note_style_choices)
}

async function savePreferences() {
    saving.value = true
    saved.value = false
    try {
        await fetch('/pdf-export/api/settings/', {
            method: 'POST',
            credentials: 'same-origin',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': getCookie('csrftoken'),
            },
            body: JSON.stringify(prefs.value),
        })
        saved.value = true
    } finally {
        saving.value = false
    }
}

onMounted(loadPreferences)
</script>
