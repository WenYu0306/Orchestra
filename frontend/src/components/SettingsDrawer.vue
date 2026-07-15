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

function toggleCity(i) { myCities.value[i].on = !myCities.value[i].on }

function applyAndClose() {
  emit('apply', {
    cities: myCities.value.filter(c => c.on).map(c => ({ name: c.name, min_salary: minSalary.value })),
  })
  emit('close')
}
</script>

<template>
  <Transition name="overlay">
    <div v-if="visible" class="drawer-overlay" @click.self="emit('close')">
      <Transition name="panel">
        <aside v-if="visible" class="drawer">
          <div class="drawer-head">
            <div>
              <h3 class="drawer-title">求职设置</h3>
              <p class="drawer-sub">调整搜索城市、薪资和分层规则</p>
            </div>
            <button class="drawer-close" @click="emit('close')">
              <svg viewBox="0 0 14 14" width="14" height="14">
                <path d="M3 3 L11 11 M11 3 L3 11" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round"/>
              </svg>
            </button>
          </div>

          <div class="drawer-body">
            <!-- 城市 -->
            <label class="sec-label">搜索城市</label>
            <div class="city-chips">
              <button v-for="(c, i) in myCities" :key="c.name"
                class="chip" :class="{ active: c.on }" @click="toggleCity(i)">{{ c.name }}</button>
            </div>

            <!-- 薪资 -->
            <label class="sec-label">
              最低薪资 <span class="salary-val">{{ minSalary }}</span> 元/月
            </label>
            <div class="slider-wrap">
              <input type="range" v-model.number="minSalary" min="5000" max="50000" step="1000" />
            </div>
            <span class="sec-hint">低于此薪资的岗位将被过滤</span>
          </div>

          <button class="apply-btn" @click="applyAndClose">应用</button>
        </aside>
      </Transition>
    </div>
  </Transition>
</template>

<style scoped>
/* ---- overlay ---- */
.drawer-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,0.12);
  display: flex; justify-content: flex-end;
}
.overlay-enter-active, .overlay-leave-active { transition: opacity .25s ease; }
.overlay-enter-from, .overlay-leave-to { opacity: 0; }

/* ---- drawer ---- */
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
.panel-enter-active, .panel-leave-active { transition: transform .3s cubic-bezier(.2,.8,.2,1); }
.panel-enter-from, .panel-leave-to { transform: translateX(100%); }

/* ---- head ---- */
.drawer-head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.drawer-title { font-family: var(--font-en); font-size: 16px; font-weight: 600; color: var(--text-1); }
.drawer-sub { font-size: 11.5px; color: var(--text-4); margin-top: 2px; }
.drawer-close {
  width: 32px; height: 32px; display: flex; align-items: center; justify-content: center;
  background: #F1F5F9; border-radius: 10px; cursor: pointer; color: var(--text-3);
  flex-shrink: 0;
}

/* ---- body ---- */
.drawer-body { flex: 1; overflow-y: auto; display: flex; flex-direction: column; gap: 18px; }
.sec-label { font-size: 12px; font-weight: 500; color: #475569; }
.salary-val { font-family: var(--font-mono); font-size: 20px; font-weight: 700; color: var(--indigo-dark); margin-left: 4px; }
.sec-hint { font-size: 11px; color: var(--text-4); }

/* ---- chips ---- */
.city-chips { display: flex; gap: 8px; flex-wrap: wrap; }
.chip {
  padding: 7px 13px; border-radius: 999px; font-size: 12.5px; font-weight: 500;
  background: #fff; border: 1px solid #E0E5EA; color: var(--text-3);
  cursor: pointer; transition: all .2s;
}
.chip.active { background: var(--indigo); color: #fff; border-color: var(--indigo); font-weight: 600; }

/* ---- slider ---- */
.slider-wrap input[type="range"] {
  width: 100%; accent-color: var(--indigo);
}

/* ---- button ---- */
.apply-btn {
  height: 42px; background: var(--indigo); color: #fff;
  border-radius: 12px; font-size: 14px; font-weight: 600;
  cursor: pointer; border: none; width: 100%; flex-shrink: 0;
}
.apply-btn:hover { opacity: 0.88; }
</style>
