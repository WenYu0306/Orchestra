<script setup>
import { ref, computed, onMounted, onUnmounted, onErrorCaptured } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import { play } from 'cuelume'
import TopBar from './components/TopBar.vue'
import JobList from './components/JobList.vue'
import BottomBar from './components/BottomBar.vue'
import SettingsDrawer from './components/SettingsDrawer.vue'
import OnboardingWizard from './components/OnboardingWizard.vue'

const status = ref('idle')
const runningMsg = ref('就绪')
const jobs = ref([])
const progress = ref(0)
const step = ref('等待启动')
const stepMeta = ref('点击「开始」运行 Agent')
const elapsedSec = ref(0)
const delivered = ref(0)
let sse = null
let sseRetry = 0
let sseRetryTimer = null
let timer = null
let uidSeq = 0

const matched = computed(() => jobs.value.length)
const sendableCount = computed(() => jobs.value.filter(j => j.status !== 'review_only').length)
const elapsed = computed(() => fmt(elapsedSec.value))
function fmt(s) { const m = Math.floor(s/60).toString().padStart(2,'0'); const ss = (s%60).toString().padStart(2,'0'); return `${m}:${ss}` }

function notify(text, type = 'success', actionable = false) {
  if (type === 'error' && actionable) {
    ElNotification({ title: '出错了', message: text + '（点击本条打开设置）', type: 'error',
                     duration: 0, onClick: () => { showSettings.value = true } })
  } else {
    ElMessage({ message: text, type, duration: 4000, showClose: true })
  }
}

function jobFromRecord(d) {
  return {
    uid: ++uidSeq,
    title: d.position || d.title || '?',
    company: d.company || '?',
    score: d.score || 0,
    tier: d.tier || 'try',
    reason: d.reason || '',
    salary: d.salary || '',
    search_city: d.search_city || '',
    search_kw: d.search_kw || '',
    greeting: d.greeting || '',
    greetingIsDefault: !!d.greeting_is_default,
    status: d.status || 'dry_run',
    securityId: d.security_id || d.securityId || '',
    encryptJobId: d.encrypt_job_id || d.encryptJobId || '',
    _selected: false,
  }
}

function connectSSE() {
  if (sse) { sse.close(); sse = null }
  sse = new EventSource('/api/events')
  sse.onopen = () => { sseRetry = 0 }
  sse.addEventListener('status', e => {
    const d = JSON.parse(e.data)
    status.value = d.status
    if (d.message) runningMsg.value = d.message
    step.value = d.message || step.value
    const dm = (d.message||'').match(/重新评分:\s*(\d+)\/(\d+)/)
    stepMeta.value = dm ? `详情重评 ${dm[1]}/${dm[2]}` : `已匹配 ${matched.value} 个`
    if (dm) progress.value = Math.min(parseInt(dm[1]) / parseInt(dm[2]) * 100, 99)
  })
  sse.addEventListener('record', e => {
    const d = JSON.parse(e.data)
    jobs.value.push(jobFromRecord(d))
    status.value = 'running'
    progress.value = Math.min((matched.value / 250) * 100, 95)
    step.value = `正在评估「${d.company || '?'} · ${d.position || '?'}」`
    stepMeta.value = `已匹配 ${matched.value} 个 · DeepSeek 打分中`
  })
  sse.addEventListener('complete', e => {
    const d = JSON.parse(e.data)
    if (d.total_sent !== undefined) {
      const ok = d.total_sent || 0; const fail = d.total_failed || 0
      delivered.value += ok
      play(fail ? "error" : "success")
      notify(`发送完成：${ok} 成功${fail ? `，${fail} 失败（失败的可重试）` : ''}`, fail ? 'error' : 'success')
      status.value = 'completed'
    } else if (d.jobs && d.jobs.length) {
      const prevSel = new Set(jobs.value.filter(j => j._selected).map(j => j.company + '|' + j.title))
      jobs.value = d.jobs.map(j => {
        const card = jobFromRecord(j)
        if (prevSel.has(card.company + '|' + card.title)) card._selected = true
        return card
      })
      status.value = 'done'
      progress.value = 100
      step.value = '评估完成 · 勾选要发送的职位'
      stepMeta.value = `共 ${d.total_applied || jobs.value.length} 个匹配`
      if (timer) { clearInterval(timer); timer = null }
    }
  })
  sse.addEventListener('error', e => {
    if (!e.data) return
    try {
      const d = JSON.parse(e.data)
      if (d && d.message) { play('error'); notify(d.message, 'error', /Key|余额/.test(d.message)) }
    } catch { /* 非 JSON 数据忽略 */ }
  })
  sse.onerror = () => {
    if (['done', 'idle', 'completed', 'error'].includes(status.value)) return
    sseRetry++
    if (sseRetry > 10) {
      status.value = 'error'
      if (timer) { clearInterval(timer); timer = null }
      notify('后端连接中断，请刷新页面', 'error')
    } else {
      if (sseRetryTimer) clearTimeout(sseRetryTimer)
      sseRetryTimer = setTimeout(connectSSE, Math.min(5000 * sseRetry, 30000))
    }
  }
}

async function fetchStatus() {
  try {
    const r = await (await fetch('/api/status')).json()
    status.value = r.status || 'idle'
    const rr = await fetch('/api/records')
    if (rr.ok) {
      const data = await rr.json()
      const recs = data.records || []
      jobs.value = recs.map(jobFromRecord)
      delivered.value = recs.filter(x => x.status === 'sent').length
      if (recs.length && status.value === 'running') {
        progress.value = Math.min((jobs.value.length / 250) * 100, 95)
      }
    }
    const sr = await fetch('/api/settings')
    if (sr.ok) {
      const st = await sr.json()
      if (!st.wizard_done) showWizard.value = true
    }
  } catch (e) {
    status.value = 'error'
    notify('后端不可达，请确认服务已启动', 'error')
  }
}

async function handleStart() {
  jobs.value = []
  progress.value = 0; elapsedSec.value = 0; delivered.value = 0
  step.value = '正在初始化...'; stepMeta.value = '启动浏览器'
  if (timer) clearInterval(timer)
  timer = setInterval(() => { elapsedSec.value++ }, 1000)
  try {
    const r = await fetch('/api/start', { method: 'POST' })
    if (!r.ok) {
      const d = await r.json().catch(() => ({}))
      notify(d.detail || '启动失败', 'error', /Key|余额/.test(d.detail || ''))
    }
  } catch (e) { notify('启动失败: ' + (e.message || e), 'error') }
}

async function handleStop() {
  if (timer) { clearInterval(timer); timer = null }
  progress.value = 0; step.value = '已停止'; stepMeta.value = '等待重新启动'
  try { await fetch('/api/stop', { method: 'POST' }) }
  catch (e) { notify('停止请求失败：后端不可达', 'error') }
}

async function handleSend(jobs) {
  const toSend = jobs
  if (toSend.length === 0) return
  status.value = 'running'
  step.value = '正在发送招呼语...'
  stepMeta.value = `选中 ${toSend.length} 个（每条间隔约1-2分钟，模拟真人）`
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
      notify(d.detail || '发送失败', 'error')
      return
    }
    const d = await r.json()
    const byCompany = new Map((d.results || []).map(x => [x.company, x]))
    toSend.forEach(j => {
      const res = byCompany.get(j.company)
      if (res && res.ok) { j._sent = true; j._sendFailed = false }
      else { j._sent = false; j._sendFailed = true }
    })
    const ok = d.sent || 0
    if (d.total && ok < d.total) {
      notify(`发送完成：${ok}/${d.total} 成功，失败的可稍后重试`, 'error')
    }
  } catch (e) {
    notify('发送失败: ' + (e.message || e), 'error')
  }
}

onMounted(() => { fetchStatus(); connectSSE() })
onUnmounted(() => {
  if (sse) sse.close()
  if (timer) { clearInterval(timer); timer = null }
  if (sseRetryTimer) clearTimeout(sseRetryTimer)
})
onErrorCaptured((err) => {
  console.error('Frontend error:', err)
  notify('界面异常: ' + (err.message || err), 'error')
  return false
})

const showSettings = ref(false)
const showWizard = ref(false)
async function onWizardDone({ startRun }) {
  showWizard.value = false
  await fetchStatus()
  if (startRun) handleStart()
}
function saveSettings(sel) {
  const names = sel?.cities || []
  showSettings.value = false
  notify('设置已保存，下次运行即按新设置搜索')
}
</script>

<template>
  <div class="page">
    <el-card shadow="never" class="panel">
      <TopBar :status="status" :matched="matched"
              @start="handleStart" @stop="handleStop" @gear="showSettings = true" />
      <div class="narrative">
        <div class="headline" v-if="matched">
          今天为你找到 <b>{{ matched }}</b> 个岗位，<b class="hot">{{ sendableCount }}</b> 个值得投
        </div>
        <div class="headline" v-else-if="status === 'running'">AI 正在为你看岗位，已看 {{ matched }} 个…</div>
        <div class="headline" v-else>准备好开始今天的求职了</div>
        <div class="narrative-sub">
          <span>已运行 {{ elapsed }}</span><i class="sep"></i>
          <span>{{ step }}{{ stepMeta ? `，${stepMeta}` : '' }}</span><i class="sep"></i>
          <span>已发送 {{ delivered }} 条</span>
        </div>
      </div>
    </el-card>

    <el-card shadow="never" class="panel list-panel">
      <JobList :jobs="jobs" :loading="status === 'running'" @send="handleSend" />
    </el-card>

    <BottomBar :matched="matched" :delivered="delivered" />

    <SettingsDrawer :visible="showSettings" @close="showSettings = false" @save="saveSettings" />
    <OnboardingWizard :visible="showWizard" @done="onWizardDone" />
  </div>
</template>

<style scoped>
.page { max-width: 1440px; margin: 0 auto; padding: 16px 32px 8px; }
.panel { border-radius: 10px; }
.narrative { padding: 14px 0 6px; }
.headline { font-size: 22px; font-weight: 800; letter-spacing: -0.01em; }
.headline b { font-variant-numeric: tabular-nums; }
.headline b.hot { color: #0d7a5f; }
.narrative-sub {
  display: flex; align-items: center; gap: 10px;
  font-size: 12px; color: var(--el-text-color-secondary);
  margin-top: 6px; font-variant-numeric: tabular-nums;
}
.narrative-sub .sep { width: 1px; height: 12px; background: var(--el-border-color); }
.list-panel { margin-top: 12px; flex: 1; }
.list-panel :deep(.el-card__body) { padding-bottom: 6px; }
</style>
