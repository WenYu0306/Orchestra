<script setup>
import { ref } from 'vue'

const props = defineProps({ visible: Boolean })
const emit = defineEmits(['close', 'apply'])

const myCities = ref([
  { name: '北京', on: true }, { name: '上海', on: false },
  { name: '长春', on: true }, { name: '深圳', on: false },
  { name: '杭州', on: false }, { name: '成都', on: false },
])
const minSalary = ref(15000)
const highThreshold = ref(80)
const mediumThreshold = ref(60)

function toggleCity(i) { myCities.value[i].on = !myCities.value[i].on }

function applyAndClose() {
  emit('apply', {
    cities: myCities.value.filter(c => c.on).map(c => ({ name: c.name, min_salary: minSalary.value })),
    thresholds: { high: highThreshold.value, medium: mediumThreshold.value },
  })
  emit('close')
}
</script>

<template>
  <div v-if="visible" class="drawer-overlay" @click.self="emit('close')">
    <Transition name="panel">
      <aside class="drawer" v-if="visible">
        <div class="drawer-head">
          <h3 class="drawer-title">求职设置</h3>
          <button class="drawer-close" @click="emit('close')">
            <svg viewBox="0 0 14 14" width="14" height="14">
              <path d="M3 3 L11 11 M11 3 L3 11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
            </svg>
          </button>
        </div>

        <div class="drawer-body">
          <div class="section">
            <span class="section-label">搜索城市</span>
            <div class="city-chips">
              <button v-for="(c, i) in myCities" :key="c.name"
                class="chip" :class="{ active: c.on }" @click="toggleCity(i)">{{ c.name }}</button>
            </div>
          </div>
          <div class="section">
            <label class="section-label">
              最低薪资 <span class="salary-val">{{ minSalary }}</span> 元/月
            </label>
            <input class="slider" type="range" v-model.number="minSalary" min="5000" max="50000" step="1000" />
          </div>
          <div class="section">
            <span class="section-label">分层阈值</span>
            <div class="threshold-row">
              <span class="tier-dot" style="background:var(--indigo)"></span>
              <span class="tier-name">高分 ≥</span>
              <input class="tier-inp" type="number" v-model.number="highThreshold" />
              <span class="tier-name">中分 ≥</span>
              <input class="tier-inp" type="number" v-model.number="mediumThreshold" />
              <span class="tier-hint">以下为可试</span>
            </div>
          </div>
        </div>

        <button class="apply-btn" @click="applyAndClose">应用</button>
      </aside>
    </Transition>
  </div>
</template>

<style scoped>
.drawer-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,0.12);
  display: flex; justify-content: flex-end;
}
.drawer {
  width: 440px; max-width: 90vw; height: 100%;
  padding: 24px; display: flex; flex-direction: column; gap: 22px;
  background: rgba(255,255,255,0.62);
  backdrop-filter: blur(24px); -webkit-backdrop-filter: blur(24px);
  border-left: 1px solid rgba(255,255,255,0.5);
  border-radius: 20px 0 0 20px;
  box-shadow:
    inset 0 1px 2px rgba(255,255,255,0.3),
    0 12px 36px rgba(0,0,0,0.06);
}
.drawer-head { display: flex; align-items: center; justify-content: space-between; }
.drawer-title { font-family: var(--font-en); font-size: 16px; font-weight: 600; color: var(--text-1); }
.drawer-close {
  width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
  background: #F1F5F9; border-radius: 10px; cursor: pointer; color: var(--text-3);
}

.drawer-body { display: flex; flex-direction: column; gap: 22px; flex: 1; overflow-y: auto; }
.section { display: flex; flex-direction: column; gap: 8px; }
.section-label { font-size: 12px; font-weight: 500; color: #475569; }
.salary-val { font-family: var(--font-mono); font-size: 20px; font-weight: 700; color: #4F46E5; }

.city-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
  padding: 7px 13px; border-radius: 999px; font-size: 12.5px;
  background: #fff; border: 1px solid #E0E5EA; color: var(--text-3);
  cursor: pointer; transition: all .2s; font-weight: 500;
}
.chip.active { background: var(--indigo); color: #fff; border-color: var(--indigo); font-weight: 600; }

.slider { width: 100%; accent-color: var(--indigo); }

.threshold-row { display: flex; align-items: center; gap: 8px; }
.tier-dot { width: 10px; height: 10px; border-radius: 999px; flex-shrink: 0; }
.tier-name { font-size: 13px; font-weight: 600; color: var(--text-3); }
.tier-inp {
  width: 52px; height: 28px; border: 1px solid var(--border); border-radius: 8px;
  text-align: center; font-family: var(--font-mono); font-size: 12px; color: var(--text-3);
}
.tier-hint { font-size: 11px; color: var(--text-5); }

.apply-btn {
  height: 42px; background: var(--indigo); color: #fff;
  border-radius: 12px; font-size: 14px; font-weight: 600;
  cursor: pointer; border: none; width: 100%;
}
.apply-btn:hover { opacity: 0.88; }

/* 抽屉滑入 */
.panel-enter-active, .panel-leave-active { transition: transform .3s cubic-bezier(.2,.8,.2,1); }
.panel-enter-from, .panel-leave-to { transform: translateX(100%); }
</style>
