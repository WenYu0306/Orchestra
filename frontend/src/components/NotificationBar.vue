<template>
  <transition name="slide">
    <n-alert
      v-if="notification"
      :type="notification.type"
      :title="notification.title"
      :closable="true"
      @close="$emit('close')"
    >
      {{ notification.message }}
    </n-alert>
  </transition>
</template>

<script setup>
import { watch, ref, onUnmounted } from 'vue'
import { NAlert } from 'naive-ui'

const props = defineProps({
  notification: { type: Object, default: null },
})

const emit = defineEmits(['close'])

let dismissTimer = null

// 有 duration 的自动消失
watch(
  () => props.notification,
  (val) => {
    if (dismissTimer) {
      clearTimeout(dismissTimer)
      dismissTimer = null
    }
    if (val && val.duration && val.duration > 0) {
      dismissTimer = setTimeout(() => {
        emit('close')
        dismissTimer = null
      }, val.duration)
    }
  }
)

onUnmounted(() => {
  if (dismissTimer) {
    clearTimeout(dismissTimer)
  }
})
</script>

<style scoped>
.slide-enter-active,
.slide-leave-active {
  transition: all 0.3s ease;
}

.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}
</style>
