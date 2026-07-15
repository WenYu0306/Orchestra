<script setup>
import { computed } from 'vue'

const props = defineProps({
  progress: { type: Number, default: 0 },
  step: { type: String, default: '等待启动' },
  stepMeta: { type: String, default: '' },
  elapsed: { type: String, default: '00:00' },
  remaining: { type: String, default: '00:00' },
})

const fillWidth = computed(() => `${props.progress}%`)
</script>

<template>
  <div class="progress-band glass">
    <div class="elapsed">
      <div class="elapsed-row">
        <span class="lbl">已运行</span>
        <span class="val">{{ elapsed }}</span>
      </div>
      <div class="remain">预计剩余 {{ remaining }} · 共约 12:00</div>
    </div>

    <div class="track">
      <div class="fill" :style="{ width: fillWidth }"></div>
    </div>

    <div class="step">
      <div class="step-text">{{ step }}</div>
      <div class="step-meta">{{ stepMeta }}</div>
    </div>
  </div>
</template>

<style scoped>
.progress-band {
  display: flex; align-items: center; gap: 28px;
  height: 73px;
  padding: 0 32px;
  margin: 0;
  border-radius: 20px;
  box-shadow:
    inset 0 1px 2px rgba(255,255,255,0.3),
    inset 0 2px 8px rgba(16,185,129,0.1),
    0 6px 20px rgba(0,0,0,0.06);
}

.elapsed { display: flex; flex-direction: column; gap: 4px; flex-shrink: 0; }
.elapsed-row { display: flex; align-items: baseline; gap: 6px; }
.lbl { font-size: 12px; color: var(--text-3); }
.val {
  font-family: var(--font-mono); font-weight: 600; font-size: 16px;
  color: var(--green-dark);
}
.remain { font-size: 11px; color: var(--text-4); }

.track {
  flex: 1; height: 6px;
  background: #E0E5EA;
  border-radius: 999px;
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(to right, var(--green) 0%, var(--blue) 50%, #A5F3FC 100%);
  transition: width .6s ease;
}

.step { display: flex; flex-direction: column; align-items: flex-end; gap: 3px; flex-shrink: 0; }
.step-text { font-size: 13px; font-weight: 500; color: var(--text-2); }
.step-meta { font-size: 11px; color: var(--text-4); }
</style>
