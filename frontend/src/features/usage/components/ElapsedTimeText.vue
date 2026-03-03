<template>
  <span class="tabular-nums">{{ displayText }}</span>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{
  createdAt?: string | null
  status?: string | null
  responseTimeMs?: number | null
  precision?: number
  intervalMs?: number
}>(), {
  createdAt: null,
  status: null,
  responseTimeMs: null,
  precision: 2,
  intervalMs: 200
})

const now = ref(Date.now())
const precision = computed(() => Math.max(0, props.precision))
const isActive = computed(() => props.status === 'pending' || props.status === 'streaming')

let timer: ReturnType<typeof setInterval> | null = null

function parseCreatedAtMs(value: string | null | undefined): number {
  if (!value) return Number.NaN
  // 后端有时返回无时区时间，按 UTC 解析，和列表时间显示逻辑保持一致
  const normalized = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`
  return new Date(normalized).getTime()
}

function stopTimer() {
  if (!timer) return
  clearInterval(timer)
  timer = null
}

function startTimer() {
  stopTimer()
  const intervalMs = Math.max(100, props.intervalMs)
  timer = setInterval(() => {
    now.value = Date.now()
  }, intervalMs)
}

watch([isActive, () => props.intervalMs], ([active]) => {
  if (active) {
    now.value = Date.now()
    startTimer()
  } else {
    stopTimer()
  }
}, { immediate: true })

onUnmounted(() => {
  stopTimer()
})

const displayText = computed(() => {
  if (!isActive.value) {
    if (props.responseTimeMs == null) return '-'
    return `${(props.responseTimeMs / 1000).toFixed(precision.value)}s`
  }

  if (!props.createdAt) return '-'

  const createdAtMs = parseCreatedAtMs(props.createdAt)
  if (Number.isNaN(createdAtMs)) return '-'

  const elapsedMs = Math.max(0, now.value - createdAtMs)
  return `${(elapsedMs / 1000).toFixed(precision.value)}s`
})
</script>
