<script setup>
import { computed } from 'vue'
const props = defineProps({ jobs: Array })

const stats = computed(() => {
  const high = props.jobs.filter(j => j.tier === 'high').length
  const medium = props.jobs.filter(j => j.tier === 'medium').length
  const try_ = props.jobs.filter(j => j.tier === 'try').length
  const total = props.jobs.length
  const pct = n => total ? ((n / total) * 100).toFixed(1) : '0.0'
  return [
    { key: 'high', label: '高分职位', value: high, sub: `≥ 80 分 · 占比 ${pct(high)}%`, color: 'var(--indigo)' },
    { key: 'medium', label: '中分职位', value: medium, sub: `60 – 79 分 · 占比 ${pct(medium)}%`, color: 'var(--blue)' },
    { key: 'try', label: '可试职位', value: try_, sub: `40 – 59 分 · 占比 ${pct(try_)}%`, color: 'var(--amber)' },
    { key: 'total', label: '候选总数', value: total, sub: '全部搜索词 · 实时更新', color: 'var(--text-1)' },
  ]
})
</script>

<template>
  <div class="stat-row">
    <div class="stat-card" v-for="s in stats" :key="s.key">
      <div class="card-top">
        <span class="label">{{ s.label }}</span>
        <svg class="ico" viewBox="0 0 18 18" width="18" height="18" :style="{ color: s.color }">
          <template v-if="s.key === 'high'">
            <path d="M9 2 L11 7 L16 7 L12 10.5 L13.5 15.5 L9 12.5 L4.5 15.5 L6 10.5 L2 7 L7 7 Z" fill="currentColor" />
          </template>
          <template v-else-if="s.key === 'medium'">
            <path d="M3 13 L7 9 L10 11 L15 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
            <circle cx="15" cy="5" r="1.6" fill="currentColor" />
          </template>
          <template v-else-if="s.key === 'try'">
            <path d="M5 16 L5 3 M5 3 L13 5.5 L5 8" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" />
          </template>
          <template v-else>
            <rect x="3" y="3" width="12" height="2.5" rx="1" fill="currentColor" />
            <rect x="3" y="8" width="12" height="2" rx="1" fill="currentColor" opacity="0.6" />
            <rect x="3" y="12.5" width="12" height="2" rx="1" fill="currentColor" opacity="0.4" />
          </template>
        </svg>
      </div>
      <div class="value" :style="{ color: s.color }">
        <Transition mode="out-in" name="pop"><span :key="s.value">{{ s.value }}</span></Transition>
      </div>
      <div class="sub">{{ s.sub }}</div>
    </div>
  </div>
</template>

<style scoped>
.stat-row { display:flex; gap:16px; padding:24px 32px; }
.stat-card { flex:1; display:flex; flex-direction:column; gap:10px; height:148px; padding:20px; background:var(--card-bg); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); border:1px solid var(--border-soft); border-radius:20px; box-shadow:inset 0 1px 0 rgba(255,255,255,0.4),0 6px 16px rgba(0,0,0,0.07),0 12px 24px rgba(0,0,0,0.03); }
.card-top { display:flex; align-items:center; justify-content:space-between; }
.label { font-size:13px; font-weight:500; color:var(--text-2); }
.ico { flex-shrink:0; }
.value { font-family:var(--font-mono); font-weight:700; font-size:40px; line-height:1.1; display:flex; align-items:center; }
.sub { font-size:12px; color:var(--text-3); }
.pop-enter-active { transition:transform .3s ease,opacity .3s ease; }
.pop-enter-from { transform:translateY(-6px) scale(.9); opacity:0; }
</style>
