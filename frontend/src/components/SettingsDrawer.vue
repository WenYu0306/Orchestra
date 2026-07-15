<script setup>
import { ref, computed } from 'vue'

defineProps({ visible: Boolean })
const emit = defineEmits(['close', 'apply'])

const cities = ref([
  { name: '北京', selected: true },
  { name: '上海', selected: true },
  { name: '深圳', selected: true },
  { name: '杭州', selected: false },
  { name: '广州', selected: false },
  { name: '成都', selected: false },
])
function toggleCity(c) { c.selected = !c.selected }

const salaryMin = ref(15)
const salaryMax = ref(60)
const trackMin = 0
const trackMax = 100
const fillLeft = computed(() => (salaryMin.value / trackMax) * 100)
const fillRight = computed(() => 100 - (salaryMax.value / trackMax) * 100)

const tiers = [
  { label: '高分档', range: '≥ 80 分', color: '#4F46E5' },
  { label: '中分档', range: '60 – 79 分', color: '#3B82F6' },
  { label: '可试档', range: '40 – 59 分', color: '#F59E0B' },
]

function onApply() {
  emit('apply')
  emit('close')
}
</script>
<template>
  <Transition name="drawer">
    <aside v-if="visible" class="drawer">
      <header class="head">
        <div class="title-group">
          <h2 class="title">搜索设置</h2>
          <p class="subtitle">调整后实时筛选职位</p>
        </div>
        <button class="close-btn" @click="emit('close')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M6 6l12 12M18 6L6 18" stroke="#64748B" stroke-width="2.2" stroke-linecap="round"/>
          </svg>
        </button>
      </header>
      <section class="section">
        <label class="section-label">搜索城市  ·  可多选</label>
        <div class="chips">
          <button
            v-for="c in cities"
            :key="c.name"
            class="chip"
            :class="{ active: c.selected }"
            @click="toggleCity(c)"
          >
            {{ c.name }}
          </button>
        </div>
      </section>
      <section class="section">
        <label class="section-label">期望薪资范围  ·  月薪</label>
        <div class="salary-value-row">
          <span class="salary-value">{{ salaryMin }}K – {{ salaryMax }}K</span>
          <span class="salary-hint">共筛选 32 个岗位</span>
        </div>
        <div class="slider-track">
          <div class="slider-bg"></div>
          <div
            class="slider-fill"
            :style="{ left: fillLeft + '%', right: fillRight + '%' }"
          ></div>
          <input
            type="range"
            class="range range-min"
            v-model.number="salaryMin"
            :min="trackMin"
            :max="trackMax"
          />
          <input
            type="range"
            class="range range-max"
            v-model.number="salaryMax"
            :min="trackMin"
            :max="trackMax"
          />
        </div>
      </section>
      <section class="section">
        <label class="section-label">匹配档位阈值</label>
        <div v-for="t in tiers" :key="t.label" class="tier-row">
          <span class="tier-label" :style="{ color: t.color }">{{ t.label }}</span>
          <span class="tier-value">{{ t.range }}</span>
        </div>
      </section>
      <div class="actions">
        <button class="apply-btn" @click="onApply">应用筛选</button>
      </div>
    </aside>
  </Transition>
</template>
<style scoped>
.drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 440px;
  height: 100vh;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 22px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 20px 0 0 20px;
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.06);
  box-sizing: border-box;
  z-index: 50;
}
.drawer-enter-active,
.drawer-leave-active {
  transition: transform 0.3s ease;
}
.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(100%);
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title-group {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.title {
  margin: 0;
  font-family: 'Geist', sans-serif;
  font-size: 16px;
  font-weight: 600;
  color: #1e293b;
}
.subtitle {
  margin: 0;
  font-size: 11.5px;
  color: #94a3b8;
}
.close-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f1f5f9;
  border: none;
  border-radius: 10px;
  cursor: pointer;
}
.section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.section-label {
  font-size: 12px;
  font-weight: 500;
  color: #475569;
}
.chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.chip {
  padding: 7px 13px;
  font-size: 12.5px;
  font-weight: 500;
  border-radius: 999px;
  cursor: pointer;
  border: 1px solid #e0e5ea;
  background: #ffffff;
  color: #64748b;
  transition: all 0.15s;
}
.chip.active {
  background: #6366f1;
  border-color: #6366f1;
  color: #ffffff;
  font-weight: 600;
}
.salary-value-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.salary-value {
  font-family: 'Geist Mono', monospace;
  font-size: 20px;
  font-weight: 700;
  color: #4f46e5;
}
.salary-hint {
  font-size: 11px;
  color: #94a3b8;
}
.slider-track {
  position: relative;
  width: 100%;
  height: 28px;
}
.slider-bg {
  position: absolute;
  top: 12px;
  left: 0;
  right: 0;
  height: 4px;
  background: #e2e8f0;
  border-radius: 999px;
}
.slider-fill {
  position: absolute;
  top: 12px;
  height: 4px;
  background: #6366f1;
  border-radius: 999px;
}
.range {
  position: absolute;
  top: 6px;
  left: 0;
  width: 100%;
  height: 16px;
  margin: 0;
  background: none;
  pointer-events: none;
  -webkit-appearance: none;
  appearance: none;
}
.range::-webkit-slider-thumb {
  -webkit-appearance: none;
  pointer-events: auto;
  width: 16px;
  height: 16px;
  border-radius: 999px;
  background: #ffffff;
  border: 2px solid #6366f1;
  cursor: pointer;
}
.range::-moz-range-thumb {
  pointer-events: auto;
  width: 16px;
  height: 16px;
  border-radius: 999px;
  background: #ffffff;
  border: 2px solid #6366f1;
  cursor: pointer;
}
.tier-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.tier-label {
  font-size: 13px;
  font-weight: 600;
}
.tier-value {
  font-family: 'Geist Mono', monospace;
  font-size: 12px;
  font-weight: 500;
  color: #64748b;
}
.actions {
  margin-top: auto;
}
.apply-btn {
  width: 100%;
  height: 42px;
  background: #6366f1;
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.apply-btn:hover {
  background: #4f46e5;
}
</style>
