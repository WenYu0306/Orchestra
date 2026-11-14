<script setup>
import { computed } from 'vue'

const props = defineProps({ status: String, matched: Number })
const emit = defineEmits(['start', 'stop', 'gear'])

const running = computed(() => props.status === 'running')
const statusText = computed(() => {
  switch (props.status) {
    case 'running': return `运行中 · 已匹配 ${props.matched} 个`
    case 'done': return `已完成 · 共匹配 ${props.matched} 个`
    case 'error': return '出错了 · 详见下方提示'
    case 'completed': return '已发送完成'
    default: return '就绪 · 等待启动'
  }
})
const statusType = computed(() => {
  switch (props.status) {
    case 'running': case 'done': case 'completed': return 'success'
    case 'error': return 'danger'
    default: return 'info'
  }
})
</script>

<template>
  <div class="top-row">
    <div class="brand">
      <span class="mark">O</span>
      <div class="brand-text">
        <b>Orchestra</b>
        <span class="sub">AI 求职助手</span>
      </div>
    </div>
    <el-tag :type="statusType" effect="light" size="large" round>{{ statusText }}</el-tag>
    <div class="grow"></div>
    <el-button text @click="emit('gear')">⚙ 设置</el-button>
    <el-button v-if="running" type="danger" plain size="large" data-cuelume-tap="close" @click="emit('stop')">停止</el-button>
    <el-button v-else type="primary" size="large" data-cuelume-tap @click="emit('start')">开始</el-button>
  </div>
</template>

<style scoped>
.top-row { display: flex; align-items: center; gap: 12px; }
.brand { display: flex; align-items: center; gap: 10px; }
.mark {
  width: 32px; height: 32px; border-radius: 8px;
  background: #1a1a1a; color: #faf7f0;
  display: grid; place-items: center;
  font-weight: 700; font-size: 16px;
}
.brand-text { display: flex; flex-direction: column; line-height: 1.2; }
.brand-text b { font-size: 18px; font-weight: 800; letter-spacing: -0.02em; }
.brand-text .sub { font-size: 12px; color: var(--el-text-color-secondary); }
.grow { flex: 1; }
</style>
