<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import TopBar from './components/TopBar.vue'
import StatCards from './components/StatCards.vue'
import JobList from './components/JobList.vue'

const status = ref('idle')
const runningMsg = ref('就绪')
const jobs = ref([])
const notif = ref(null)
let sse = null
let sseRetry = 0

const matched = computed(() => jobs.value.length)
const tierCount = t => jobs.value.filter(j => j.tier === t).length

function connectSSE() {
  sse = new EventSource('/api/events')
  sse.addEventListener('status', e => {
    const d = JSON.parse(e.data)
    status.value = d.status
    if (d.message) runningMsg.value = d.message
  })
  sse.addEventListener('record', e => {
    const d = JSON.parse(e.data)
    jobs.value.push({
      title: d.position || '?',
      company: d.company || '?',
      score: d.score || 0,
      tier: d.tier || 'try',
      reason: d.reason || '',
      salary: d.salary || '',
      search_city: d.search_city || '',
      search_kw: d.search_kw || '',
      greeting: d.greeting || '',
      status: d.status || 'dry_run',
    })
    status.value = 'running'
  })
  sse.addEventListener('complete', e => {
    const d = JSON.parse(e.data)
    if (d.jobs && d.jobs.length) jobs.value = d.jobs
    status.value = 'completed'
  })
  sse.addEventListener('error', e => {
    const d = JSON.parse(e.data)
    if (d && d.message) notif.value = { type: 'error', text: d.message }
  })
  sse.onerror = () => {
    if (status.value === 'idle' || status.value === 'completed' || status.value === 'error') return
    sseRetry++
    if (sseRetry > 10) notif.value = { type: 'error', text: '后端已断开，请手动重启' }
    else setTimeout(connectSSE, 5000)
  }
}

async function fetchStatus() {
  try { const r = await (await fetch('/api/status')).json(); status.value = r.status || 'idle' }
  catch (e) {}
}

async function handleStart() {
  try { await fetch('/api/start', { method: 'POST' }) }
  catch (e) { notif.value = { type: 'error', text: '启动失败: ' + (e.message || e) } }
}

async function handleStop() {
  try { await fetch('/api/stop', { method: 'POST' }) }
  catch (e) {}
}

onMounted(() => { import('./style.css'); fetchStatus(); connectSSE() })
onUnmounted(() => { if (sse) sse.close() })
</script>

<template>
  <div class="aurora"><div class="aurora-blob"></div></div>
  <div class="shell">
    <TopBar :status="status" :matched="matched" @start="handleStart" @stop="handleStop" />
    <StatCards :jobs="jobs" />
    <JobList :jobs="jobs" :loading="status === 'running'" />
    <Transition name="banner">
      <div v-if="notif" class="banner" :class="notif.type">
        <span class="banner-dot"></span>
        <span class="banner-text">{{ notif.text }}</span>
        <button class="banner-close" @click="notif = null">×</button>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.shell {
  position: relative; z-index: 1;
  min-height: 100vh; max-width: 1100px; margin: 0 auto;
  padding-top: 20px;
  background: linear-gradient(180deg, var(--bg-1) 0%, var(--bg-2) 30%, var(--bg-2) 100%);
  display: flex; flex-direction: column;
}
.banner {
  position: fixed; left: 50%; bottom: 56px; transform: translateX(-50%);
  display: flex; align-items: center; gap: 12px;
  max-width: 720px; padding: 14px 20px; border-radius: 14px;
  backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px);
  z-index: 50; box-shadow: 0 12px 32px rgba(0,0,0,0.12);
}
.banner-dot { width: 8px; height: 8px; border-radius: 999px; flex-shrink: 0; }
.banner-text { font-size: 13px; color: var(--text-1); flex: 1; }
.banner-close { font-size: 18px; color: var(--text-3); line-height: 1; padding: 0 4px; }
.banner.done { background: rgba(255,255,255,0.85); border: 1px solid var(--green-border); box-shadow: 0 12px 32px rgba(16,185,129,0.16); }
.banner.done .banner-dot { background: var(--green); box-shadow: 0 0 8px var(--green); }
.banner.error { background: rgba(255,255,255,0.85); border: 1px solid rgba(239,68,68,0.25); }
.banner.error .banner-dot { background: var(--red); box-shadow: 0 0 8px var(--red); }
.banner-enter-active, .banner-leave-active { transition: all .4s cubic-bezier(.2,.8,.2,1); }
.banner-enter-from, .banner-leave-to { opacity: 0; transform: translateX(-50%) translateY(20px); }
</style>
