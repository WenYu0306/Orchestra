<script setup>
const props = defineProps({ job: Object })

function tierColor(t) {
  return { high: 'var(--indigo)', medium: 'var(--blue)', try: 'var(--amber)' }[t] || 'var(--indigo)'
}
function tierSoft(t) {
  return { high: 'var(--indigo-soft)', medium: 'var(--blue-soft)', try: 'var(--amber-soft)' }[t] || 'var(--indigo-soft)'
}
function tierBorder(t) {
  return { high: 'var(--indigo-border)', medium: 'var(--blue-border)', try: 'var(--amber-border)' }[t] || 'var(--indigo-border)'
}
function tierLabel(t) {
  return { high: '高匹配', medium: '中匹配', try: '可尝试' }[t] || t
}
function companyInit(name) {
  return (name || '?').charAt(0)
}
</script>

<template>
  <article class="card">
    <span class="accent"></span>
    <div class="top">
      <div class="info">
        <div class="company-row">
          <div class="avatar" :style="{ background: tierSoft(job.tier), color: tierColor(job.tier) }">
            {{ companyInit(job.company) }}
          </div>
          <span class="company">{{ job.company || '?' }}</span>
          <span class="tier-tag" :style="{ background: tierSoft(job.tier), borderColor: tierBorder(job.tier), color: tierColor(job.tier) }">
            {{ tierLabel(job.tier) }}
          </span>
        </div>
        <div class="job-title">{{ job.title || job.position || '?' }}</div>
        <div class="meta">
          <span class="salary">{{ job.salary || '—' }}</span>
          <span class="loc">{{ job.search_city || '' }}</span>
        </div>
      </div>
      <div class="score" :style="{ color: tierColor(job.tier) }">{{ job.score }}</div>
    </div>
    <div class="reason">{{ job.reason || '' }}</div>
    <div class="greeting" v-if="job.greeting">
      <div class="greeting-head"><span class="greeting-lbl">招呼语预览</span></div>
      <div class="greeting-text">{{ job.greeting }}</div>
    </div>
  </article>
</template>

<style scoped>
.card { position:relative; display:flex; flex-direction:column; gap:14px; padding:20px; background:var(--card-bg); backdrop-filter:blur(20px); -webkit-backdrop-filter:blur(20px); border:1px solid var(--border-soft); border-radius:20px; box-shadow:inset 0 1px 0 rgba(255,255,255,0.35),0 6px 18px rgba(0,0,0,0.06),0 10px 28px rgba(0,0,0,0.03); transition:transform .28s cubic-bezier(.2,.8,.2,1),box-shadow .28s ease,border-color .28s ease; }
.card:hover { transform:scale(1.02); z-index:20; background:var(--card-bg-hover); border-color:var(--indigo-border); box-shadow:inset 0 1px 0 rgba(255,255,255,0.45),0 12px 32px rgba(99,102,241,0.16),0 18px 44px rgba(0,0,0,0.08); }
.card:hover .accent { opacity:1; }
.accent { position:absolute; left:0; top:0; bottom:0; width:4px; background:var(--indigo); border-radius:20px 0 0 20px; opacity:0; transition:opacity .28s ease; }
.top { display:flex; align-items:flex-start; justify-content:space-between; gap:20px; }
.info { flex:1; display:flex; flex-direction:column; gap:8px; min-width:0; }
.company-row { display:flex; align-items:center; gap:10px; }
.avatar { width:34px; height:34px; flex-shrink:0; display:flex; align-items:center; justify-content:center; border-radius:10px; font-size:14px; font-weight:600; }
.company { font-size:15px; font-weight:600; color:var(--text-1); }
.tier-tag { padding:3px 8px; border-radius:6px; border:1px solid; font-size:11px; font-weight:500; }
.job-title { font-size:14px; font-weight:500; color:var(--text-2); }
.meta { display:flex; align-items:center; gap:10px; }
.salary { font-family:var(--font-mono); font-weight:600; font-size:13px; color:var(--text-1); }
.loc { font-size:12px; color:var(--text-3); }
.score { font-family:var(--font-mono); font-weight:700; font-size:34px; line-height:1; flex-shrink:0; }
.reason { font-size:12px; color:var(--text-3); line-height:18px; }
.greeting { background:#F7F8FA; border:1px solid rgba(224,227,234,0.5); border-radius:12px; padding:14px; }
.greeting-head { display:flex; align-items:center; justify-content:space-between; margin-bottom:8px; }
.greeting-lbl { font-size:11px; font-weight:500; color:var(--text-3); }
.greeting-text { font-size:12.5px; color:var(--text-1); line-height:20px; }
</style>
