<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import TopBar from './components/TopBar.vue'
import ProgressBand from './components/ProgressBand.vue'
import StatCards from './components/StatCards.vue'
import JobList from './components/JobList.vue'
import BottomBar from './components/BottomBar.vue'

const status = ref('idle')
const runningMsg = ref('就绪')
const jobs = ref([])
const progress = ref(0)
const step = ref('等待启动')
const stepMeta = ref('点击「开始」运行 Agent')
const elapsedSec = ref(0)
const notif = ref(null)
let sse = null
let sseRetry = 0
let timer = null

const matched = computed(() => jobs.value.length)
const tierCount = t => jobs.value.filter(j => j.tier === t).length
const elapsed = computed(() => fmt(elapsedSec.value))
const remaining = computed(() => fmt(Math.max(0, 720 - elapsedSec.value)))
function fmt(s) { const m = Math.floor(s/60).toString().padStart(2,'0'); const ss = (s%60).toString().padStart(2,'0'); return `${m}:${ss}` }

function connectSSE() {
  sse = new EventSource('/api/events')
  sse.addEventListener('status', e => {
    const d = JSON.parse(e.data)
    status.value = d.status
    if (d.message) runningMsg.value = d.message
    step.value = d.message || step.value
    stepMeta.value = `已匹配 ${matched.value} 个`
  })
  sse.addEventListener('record', e => {
    const d = JSON.parse(e.data)
    jobs.value.push({
      title: d.position || '?',
      company: d.company || '?',
      companyInitial: (d.company || '?')[0],
      score: d.score || 0,
      tier: d.tier || 'try',
      reason: d.reason || '',
      salary: d.salary || '',
      search_city: d.search_city || '',
      search_kw: d.search_kw || '',
      location: d.search_city || '',
      greeting: d.greeting || '',
      securityId: d.security_id || '',
      encryptJobId: d.encrypt_job_id || '',
      _selected: false,
      status: d.status || 'dry_run',
    })
    status.value = 'running'
    progress.value = Math.min((matched.value / 250) * 100, 95)
    step.value = `正在评估「${d.company || '?'} · ${d.position || '?'}」`
    stepMeta.value = `已匹配 ${matched.value} 个 · DeepSeek 打分中`
  })
  sse.addEventListener('complete', e => {
    const d = JSON.parse(e.data)
    if (d.total_sent !== undefined) {
      // 发送结果
      const ok = d.total_sent || 0; const fail = d.total_failed || 0
      notif.value = { type: 'done', text: `发送完成：${ok} 成功, ${fail} 失败` }
      status.value = 'completed'
    } else if (d.jobs && d.jobs.length) {
      // 评分完成
      jobs.value = d.jobs.map(j => ({...j, companyInitial: (j.company || '?')[0], _selected: false, id: j.securityId || j.company}))
      status.value = 'done'
      progress.value = 100
      step.value = '评估完成 · 勾选要发送的职位'
      stepMeta.value = `共 ${d.total_applied || jobs.value.length} 个匹配`
      if (timer) { clearInterval(timer); timer = null }
    }
  })
  sse.addEventListener('error', e => {
    const d = JSON.parse(e.data)
    if (d && d.message) notif.value = { type: 'error', text: d.message }
  })
  sse.onerror = () => {
    if (status.value === 'done' || status.value === 'idle' || status.value === 'completed' || status.value === 'error') return
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
  jobs.value = []
  progress.value = 0; elapsedSec.value = 0
  step.value = '正在初始化...'; stepMeta.value = '启动浏览器'
  if (timer) clearInterval(timer)
  timer = setInterval(() => { elapsedSec.value++ }, 1000)
  try {
    const r = await fetch('/api/start', { method: 'POST' })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      notif.value = { type: 'error', text: '启动失败: ' + (d.detail || r.statusText) }
    }
  } catch (e) { notif.value = { type: 'error', text: '启动失败: ' + (e.message || e) } }
}

async function handleStop() {
  if (timer) { clearInterval(timer); timer = null }
  progress.value = 0; step.value = '已停止'; stepMeta.value = '等待重新启动'
  try { await fetch('/api/stop', { method: 'POST' }) }
  catch (e) {}
}

const selectedCount = computed(() => jobs.value.filter(j => j._selected).length)

async function handleSend() {
  const toSend = jobs.value.filter(j => j._selected)
  if (toSend.length === 0) return
  status.value = 'running'
  step.value = '正在发送招呼语...'
  stepMeta.value = `选中 ${toSend.length} 个`
  try {
    const r = await fetch('/api/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        jobs: toSend.map(j => ({
          securityId: j.securityId, encryptJobId: j.encryptJobId,
          greeting: j.greeting, company: j.company,
        })),
      }),
    })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      notif.value = { type: 'error', text: '发送失败: ' + (d.detail || r.statusText) }
    }
  } catch (e) {
    notif.value = { type: 'error', text: '发送失败: ' + (e.message || e) }
  }
}

const scale = ref(1)
function updateScale() {
  scale.value = Math.max(900 / 1440, Math.min(window.innerWidth / 1440, 1.4))
}
onMounted(() => { import('./style.css'); fetchStatus(); connectSSE(); updateScale(); window.addEventListener('resize', updateScale) })
onUnmounted(() => { if (sse) sse.close(); window.removeEventListener('resize', updateScale) })
</script>

<template>
  <div class="aurora"><div class="aurora-blob"></div></div>
  <div class="scaler" :style="{ transform: `scale(${scale})` }">
    <div class="shell">
      <TopBar :status="status" :matched="matched" @start="handleStart" @stop="handleStop" />
      <ProgressBand :progress="progress" :step="step" :step-meta="stepMeta" :elapsed="elapsed" :remaining="remaining" />
      <StatCards :jobs="jobs" />
      <JobList :jobs="jobs" :loading="status === 'running'" :selected-count="selectedCount" @send="handleSend" />
      <BottomBar :matched="matched" :delivered="matched" />
    <Transition name="banner">
      <div v-if="notif" class="banner" :class="notif.type">
        <span class="banner-dot"></span>
        <span class="banner-text">{{ notif.text }}</span>
        <button class="banner-close" @click="notif = null">×</button>
      </div>
    </Transition>
    </div>
  </div>
</template>

<style scoped>
.scaler {
  transform-origin: top center;
  width: 1440px;
  margin: 0 auto;
  position: relative;
  z-index: 1;
}
@media (max-width: 1440px) {
  .scaler { width: 100%; transform: none; }
}
.shell {
  min-height: 100vh;
  background: linear-gradient(180deg, var(--bg-1) 0%, var(--bg-2) 30%, var(--bg-2) 100%);
  display: flex; flex-direction: column;
}
.shell > :deep(.job-list) { flex: 1; }
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
