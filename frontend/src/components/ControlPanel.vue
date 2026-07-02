<template>
  <div class="control-panel">
    <!-- 按钮组 -->
    <div class="button-group">
      <n-button
        v-if="status !== 'need_captcha'"
        type="primary"
        size="large"
        :loading="status === 'running'"
        :disabled="status === 'running'"
        @click="$emit('start')"
      >
        {{ status === 'running' ? '投递中...' : '开始投递' }}
      </n-button>

      <n-button
        v-if="status === 'need_captcha'"
        type="warning"
        size="large"
        @click="$emit('resume')"
      >
        我已处理验证码，继续
      </n-button>

      <n-button
        v-if="status === 'running' || status === 'need_captcha'"
        type="error"
        size="large"
        ghost
        @click="$emit('stop')"
      >
        停止
      </n-button>
    </div>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card stat-high">
        <div class="stat-number">{{ tierCounts.high?.current || 0 }}/{{ tierCounts.high?.max || 5 }}</div>
        <div class="stat-label">高匹配 ≥80</div>
      </div>
      <div class="stat-card stat-medium">
        <div class="stat-number">{{ tierCounts.medium?.current || 0 }}/{{ tierCounts.medium?.max || 7 }}</div>
        <div class="stat-label">中匹配 60-79</div>
      </div>
      <div class="stat-card stat-try">
        <div class="stat-number">{{ tierCounts.try?.current || 0 }}/{{ tierCounts.try?.max || 8 }}</div>
        <div class="stat-label">可尝试 40-59</div>
      </div>
      <div class="stat-card stat-pending">
        <div class="stat-number">{{ pendingCount }}</div>
        <div class="stat-label">待选区</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { NButton } from 'naive-ui'

defineProps({
  status: { type: String, default: 'idle' },
  tierCounts: { type: Object, default: () => ({}) },
  pendingCount: { type: Number, default: 0 },
})

defineEmits(['start', 'stop', 'resume'])
</script>

<style scoped>
.control-panel {
  display: flex;
  align-items: center;
  gap: 32px;
  margin-bottom: 24px;
  padding: 16px 20px;
  background: #1E1E1E;
  border-radius: 8px;
}

.button-group {
  display: flex;
  gap: 12px;
  flex-shrink: 0;
}

.stats-row {
  display: flex;
  gap: 16px;
  flex: 1;
  justify-content: flex-end;
}

.stat-card {
  text-align: center;
  padding: 8px 16px;
  border-radius: 6px;
  background: #2A2A2A;
  min-width: 80px;
}

.stat-number {
  font-size: 22px;
  font-weight: 700;
  line-height: 1.2;
}

.stat-label {
  font-size: 11px;
  color: #999;
  margin-top: 2px;
}

.stat-high .stat-number { color: #18a058; }
.stat-medium .stat-number { color: #409eff; }
.stat-try .stat-number { color: #f0a020; }
.stat-pending .stat-number { color: #a855f7; }
</style>
