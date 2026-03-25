<template>
  <div
    class="relative group cursor-pointer"
    :class="containerClass"
  >
    <svg
      xmlns="http://www.w3.org/2000/svg"
      :viewBox="viewBox"
      class="transition-colors duration-500 ease-out"
      :class="[logoClass]"
    >
      <path
        :d="fullPath"
        fill="currentColor"
        fill-rule="evenodd"
      />
    </svg>
  </div>
</template>

<script setup lang="ts">
import { AETHER_FULL_PATH, AETHER_SVG_VIEWBOX } from '@/constants/logoPaths'

interface Props {
  size?: string
  className?: string
}

const props = withDefaults(defineProps<Props>(), {
  size: 'h-8 w-8',
  className: ''
})

const containerClass = `${props.size} ${props.className}`
const logoClass = 'w-full h-full'
const viewBox = AETHER_SVG_VIEWBOX
const fullPath = AETHER_FULL_PATH
</script>

<style scoped>
</style>
