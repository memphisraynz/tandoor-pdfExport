<template>
    <v-container>
        <v-row>
            <v-col cols="12" md="8" lg="6">
                <h1 class="mb-4">{{ $t('Export_Recipe_PDF') }}</h1>
                <p class="text-medium-emphasis mb-4">{{ $t('Export_Recipe_PDF_Help') }}</p>

                <ModelSelect model="Recipe" v-model="selectedRecipe" :label="$t('Recipe')"/>

                <v-btn
                    class="mt-4"
                    color="primary"
                    :disabled="!selectedRecipe"
                    prepend-icon="fa-solid fa-file-pdf"
                    :href="downloadUrl"
                    target="_blank"
                >
                    {{ $t('Download_PDF') }}
                </v-btn>
            </v-col>
        </v-row>
    </v-container>
</template>

<script setup lang="ts">
import {computed, ref} from 'vue'
import ModelSelect from '@/components/inputs/ModelSelect.vue'

const selectedRecipe = ref<any>(null)

const downloadUrl = computed(() => {
    if (!selectedRecipe.value) {
        return undefined
    }
    return `/pdf-export/recipe/${selectedRecipe.value.id}/pdf/`
})
</script>
