<script setup>
import { ref } from 'vue'

defineProps({ visible: Boolean })
const emit = defineEmits(['close', 'apply'])

const cities = ref([
  { name: '北京', selected: true, minSalary: '15K' },
  { name: '长春', selected: true, minSalary: '8K' },
  { name: '上海', selected: false, minSalary: '15K' },
  { name: '深圳', selected: false, minSalary: '15K' },
  { name: '杭州', selected: false, minSalary: '15K' },
  { name: '成都', selected: false, minSalary: '10K' },
])
function toggleCity(c) { c.selected = !c.selected }

function onApply() {
  const selected = cities.value.filter(c => c.selected).map(c => ({
    name: c.name,
    min_salary: parseInt(c.minSalary) * 1000,
  }))
  emit('apply', { cities: selected })
  emit('close')
}

const tiers = [
  { label: '高分档', range: '≥ 80 分', color: '#4F46E5' },
  { label: '中分档', range: '60 – 79 分', color: '#3B82F6' },
  { label: '可试档', range: '40 – 59 分', color: '#F59E0B' },
]
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
            {{ c.name }}<span class="chip-salary">{{ c.minSalary }}</span>
          </button>
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
.chip-salary {
  font-size: 10.5px;
  opacity: 0.7;
  margin-left: 4px;
}
.chip.active .chip-salary {
  opacity: 0.9;
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
