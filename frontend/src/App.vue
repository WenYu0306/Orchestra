<script setup>
import { ref, computed, onMounted, onUnmounted, onErrorCaptured } from 'vue'
import TopBar from './components/TopBar.vue'
import ProgressBand from './components/ProgressBand.vue'
import StatCards from './components/StatCards.vue'
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
const notif = ref(null)
const delivered = ref(0)
const cityFilter = ref(null)
let sse = null
let sseRetry = 0
let sseRetryTimer = null
let timer = null
let uidSeq = 0

const matched = computed(() => jobs.value.length)
const elapsed = computed(() => fmt(elapsedSec.value))
const displayJobs = computed(() =>
  cityFilter.value ? jobs.value.filter(j => cityFilter.value.has(j.location || j.search_city)) : jobs.value
)
function fmt(s) { const m = Math.floor(s/60).toString().padStart(2,'0'); const ss = (s%60).toString().padStart(2,'0'); return `${m}:${ss}` }

function jobFromRecord(d) {
  return {
    uid: ++uidSeq,
    title: d.position || d.title || '?',
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
  // 连接成功即重置重连计数（原来是累计的，10 次瞬时抖动就永久放弃）
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
      // 发送结果
      const ok = d.total_sent || 0; const fail = d.total_failed || 0
      delivered.value += ok
      notif.value = { type: fail ? 'error' : 'done', text: `发送完成：${ok} 成功${fail ? `，${fail} 失败（失败的可重试）` : ''}` }
      status.value = 'completed'
    } else if (d.jobs && d.jobs.length) {
      // 评分完成：保留用户已勾选的卡片
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
    // EventSource 原生连接错误事件没有 e.data，只有后端自定义 error 事件才有
    if (!e.data) return
    try {
      const d = JSON.parse(e.data)
      if (d && d.message) notif.value = { type: 'error', text: d.message }
    } catch { /* 非 JSON 数据忽略 */ }
  })
  sse.onerror = () => {
    if (['done', 'idle', 'completed', 'error'].includes(status.value)) return
    sseRetry++
    if (sseRetry > 10) {
      status.value = 'error'
      if (timer) { clearInterval(timer); timer = null }
      notif.value = { type: 'error', text: '后端连接中断，请刷新页面' }
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
    // 刷新/重连后恢复本次会话的卡片与已发送数（原来刷新即全部丢失）
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
    // 首次使用引导：未完成向导 → 全屏向导（风险告知→简历→Key→城市→扫码）
    const sr = await fetch('/api/settings')
    if (sr.ok) {
      const st = await sr.json()
      if (!st.wizard_done) showWizard.value = true
    }
  } catch (e) {
    status.value = 'error'
    notif.value = { type: 'error', text: '后端不可达，请确认服务已启动' }
  }
}

async function handleUploadResume(e) {
  const f = e.target.files?.[0]
  if (!f) return
  const fd = new FormData(); fd.append('file', f)
  try {
    const r = await fetch('/api/upload-resume', { method: 'POST', body: fd })
    if (r.ok) notif.value = { type: 'done', text: '简历已上传: ' + f.name }
    else notif.value = { type: 'error', text: '上传失败' }
  } catch (ee) { notif.value = { type: 'error', text: '上传失败' } }
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
      notif.value = { type: 'error', text: '启动失败: ' + (d.detail || r.statusText) }
    }
  } catch (e) { notif.value = { type: 'error', text: '启动失败: ' + (e.message || e) } }
}

async function handleStop() {
  if (timer) { clearInterval(timer); timer = null }
  progress.value = 0; step.value = '已停止'; stepMeta.value = '等待重新启动'
  try { await fetch('/api/stop', { method: 'POST' }) }
  catch (e) { notif.value = { type: 'error', text: '停止请求失败：后端不可达' } }
}

const selectedCount = computed(() => jobs.value.filter(j => j._selected).length)

async function handleSend() {
  const toSend = jobs.value.filter(j => j._selected)
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
      notif.value = { type: 'error', text: '发送失败: ' + (d.error || d.detail || r.statusText) }
    } else {
      const d = await r.json()
      // 按后端逐条结果更新卡片（原来无脑全标成功）
      const byCompany = new Map((d.results || []).map(x => [x.company, x]))
      toSend.forEach(j => {
        const res = byCompany.get(j.company)
        j._sent = !!(res && res.ok)
        j._selected = false
      })
      const ok = d.sent || 0
      // 已发送数由 SSE complete 事件统一累加（与后端 ok_count 同源），此处不重复计数
      if (d.total && ok < d.total) {
        notif.value = { type: 'error', text: `发送完成：${ok}/${d.total} 成功，失败的可稍后重试` }
      }
    }
  } catch (e) {
    notif.value = { type: 'error', text: '发送失败: ' + (e.message || e) }
  }
}

const scale = ref(1)
function updateScale() {
  scale.value = Math.max(900 / 1440, Math.min(window.innerWidth / 1440, 1.4))
}
onMounted(() => { fetchStatus(); connectSSE(); updateScale(); window.addEventListener('resize', updateScale) })
onUnmounted(() => {
  if (sse) sse.close()
  if (timer) { clearInterval(timer); timer = null }
  if (sseRetryTimer) clearTimeout(sseRetryTimer)
  window.removeEventListener('resize', updateScale)
})
onErrorCaptured((err) => {
  console.error('Frontend error:', err)
  notif.value = { type: 'error', text: '界面异常: ' + (err.message || err) }
  return false
})

const showSettings = ref(false)
const showWizard = ref(false)
const notifActionable = computed(() =>
  notif.value?.type === 'error' && /Key|余额/.test(notif.value.text))
function onBannerClick() {
  // 可操作类错误（Key 无效/余额不足）点横幅直达设置
  if (notifActionable.value) showSettings.value = true
}
async function onWizardDone({ startRun }) {
  showWizard.value = false
  await fetchStatus()
  if (startRun) handleStart()
}
function saveSettings(sel) {
  // 设置本身已由抽屉提交到 /api/settings 保存；这里联动当前列表的城市筛选
  const names = sel?.cities || []
  cityFilter.value = names.length ? new Set(names) : null
  showSettings.value = false
  notif.value = { type: 'done', text: '设置已保存，下次运行即按新设置搜索' }
}
</script>

<template>
  <div class="aurora"><div class="aurora-blob"></div></div>
  <div class="scaler" :style="{ transform: `scale(${scale})` }">
    <div class="shell">
      <TopBar :status="status" :matched="matched" @start="handleStart" @stop="handleStop" @upload-resume="handleUploadResume" @gear="showSettings = true" />
      <SettingsDrawer :visible="showSettings" @close="showSettings = false" @save="saveSettings" />
      <OnboardingWizard :visible="showWizard" @done="onWizardDone" />
      <ProgressBand :progress="progress" :step="step" :step-meta="stepMeta" :elapsed="elapsed" />
      <StatCards :jobs="jobs" :status="status" />
      <JobList :jobs="displayJobs" :loading="status === 'running'" :selected-count="selectedCount" @send="handleSend" />
      <BottomBar :matched="matched" :delivered="delivered" />
    <Transition name="banner">
      <div v-if="notif" class="banner" :class="[notif.type, { actionable: notifActionable }]"
           @click="onBannerClick">
        <span class="banner-dot"></span>
        <span class="banner-text">{{ notif.text }}</span>
        <button class="banner-close" @click.stop="notif = null">×</button>
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
.banner.actionable { cursor: pointer; }
.banner-enter-active, .banner-leave-active { transition: all .4s cubic-bezier(.2,.8,.2,1); }
.banner-enter-from, .banner-leave-to { opacity: 0; transform: translateX(-50%) translateY(20px); }
</style>
