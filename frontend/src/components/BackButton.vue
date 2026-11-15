<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'

const props = withDefaults(
  defineProps<{
    fallback: string
    label?: string
  }>(),
  { label: '返回上一页' },
)

const router = useRouter()

const canGoBack = computed(() => {
  const state = window.history.state as { back?: string | null } | null
  return Boolean(state?.back)
})

function goBack(): void {
  if (canGoBack.value) {
    router.back()
    return
  }
  void router.push(props.fallback)
}
</script>

<template>
  <button class="back-link back-button" type="button" @click="goBack">
    ← {{ label }}
  </button>
</template>
