<template>
  <n-config-provider :theme="darkTheme">
    <n-notification-provider>
      <div class="app-container">
        <header class="top-bar">
          <div class="top-bar-left">
            <h1 class="logo">JobHunter <span class="version">v1.0</span></h1>
          </div>
          <div class="top-bar-right">
            <n-tag :type="statusTagType" :bordered="false" size="large">
              <span class="status-dot" :class="statusDotClass"></span>
              {{ statusText }}
            </n-tag>
          </div>
        </header>

        <!-- 控制区 -->
        <div class="control-panel">
          <div class="button-group">
            <n-button
              v-if="status !== 'completed'"
              type="primary" size="large"
              :loading="status === 'running'"
              :disabled="status === 'running'"
              @click="handleStart"
            >
              {{ status === 'running' ? '分析中...' : '开始分析' }}
            </n-button>
            <n-button
              v-if="status === 'running'"
              type="error" size="large" ghost @click="handleStop"
            >停止</n-button>
          </div>
          <div class="stats-row">
            <div class="stat-card stat-high">
              <div class="stat-number">{{ tierCount('high') }}</div>
              <div class="stat-label">高分 ≥80</div>
            </div>
            <div class="stat-card stat-medium">
              <div class="stat-number">{{ tierCount('medium') }}</div>
              <div class="stat-label">中分 60-79</div>
            </div>
            <div class="stat-card stat-try">
              <div class="stat-number">{{ tierCount('try') }}</div>
              <div class="stat-label">可试 40-59</div>
            </div>
            <div class="stat-card stat-total">
              <div class="stat-number">{{ jobs.length }}</div>
              <div class="stat-label">推荐职位</div>
            </div>
          </div>
        </div>

        <!-- 职位推荐列表 -->
        <div class="jobs-section">
          <n-empty v-if="jobs.length === 0" description="点击「开始分析」获取推荐职位" />
          <div v-else class="job-cards">
            <div v-for="(job, i) in jobs" :key="i" class="job-card">
              <div class="jc-header">
                <div class="jc-title">{{ job.title }}</div>
                <n-tag :type="scoreType(job.score)" :bordered="false">{{ job.score }}分</n-tag>
              </div>
              <div class="jc-meta">
                <span class="jc-company">{{ job.company }}</span>
                <span v-if="job.salary" class="jc-salary">{{ job.salary }}</span>
                <span class="jc-city">{{ job.search_city }}</span>
                <span class="jc-kw">{{ job.search_kw }}</span>
              </div>
              <div class="jc-reason">📋 {{ job.reason }}</div>
              <div class="jc-greeting" v-if="job.greeting">💬 {{ job.greeting }}</div>
              <div class="jc-actions">
                <n-tag :type="tierColor(job.tier)" size="small">{{ tierLabel(job.tier) }}</n-tag>
              </div>
            </div>
          </div>
        </div>

        <!-- 通知 -->
        <div class="notif-bar" v-if="notif">
          <n-alert :type="notif.type" :title="notif.title" closable @close="notif=null">{{ notif.msg }}</n-alert>
        </div>
      </div>
    </n-notification-provider>
  </n-config-provider>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { NConfigProvider, NButton, NTag, NAlert, NEmpty, NNotificationProvider } from 'naive-ui'
import { darkTheme } from 'naive-ui'

const status = ref('idle')
const runningMsg = ref('就绪')
const jobs = ref([])
const notif = ref(null)
let sse = null

const statusTagType = computed(() =>
  ({idle:'default',running:'success',completed:'info',error:'error'}[status.value]||'default'))
const statusDotClass = computed(() => `dot-${status.value}`)
const statusText = computed(() =>
  status.value === 'running' ? runningMsg.value :
  status.value === 'completed' ? `分析完成 · ${jobs.value.length} 个推荐` :
  {idle:'就绪',error:'异常'}[status.value]||status.value)

const tierCount = (t) => jobs.value.filter(j => j.tier === t).length
const scoreType = (s) => s >= 80 ? 'success' : s >= 60 ? 'info' : 'warning'
const tierColor = (t) => ({high:'success',medium:'info',try:'warning',skip:'default'}[t]||'default')
const tierLabel = (t) => ({high:'高匹配',medium:'中匹配',try:'可尝试',skip:'跳过'}[t]||t)

function connectSSE() {
  sse = new EventSource('/api/events')
  sse.addEventListener('status', e => {
    const d = JSON.parse(e.data)
    status.value = d.status
    if (d.message) runningMsg.value = d.message
  })
  sse.addEventListener('record', e => {
    const d = JSON.parse(e.data)
    // 实时追加投递记录到列表
    jobs.value.push({
      title: d.position || '?',
      company: d.company || '?',
      score: d.score || 0,
      tier: d.tier || 'try',
      reason: d.reason || '',
      salary: '',
      search_city: '',
      search_kw: '',
      greeting: '',
      status: d.status || 'success',
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
    notif.value = {type:'error', title:'错误', msg:d.message||JSON.stringify(d)}
  })
  sse.onerror = () => {
    if (status.value === 'idle' || status.value === 'completed' || status.value === 'error') return
    setTimeout(connectSSE, 5000)
  }
}

async function fetchStatus() {
  try {
    const r = await (await fetch('/api/status')).json()
    status.value = r.status || 'idle'
  } catch(e) {}
}

async function handleStart() {
  try { await fetch('/api/start', {method:'POST'}) }
  catch(e) { notif.value = {type:'error',title:'启动失败',msg:String(e)} }
}

async function handleStop() {
  try { await fetch('/api/stop', {method:'POST'}) }
  catch(e) {}
}

onMounted(() => { fetchStatus(); connectSSE() })
onUnmounted(() => { if(sse) sse.close() })
</script>

<style>
:root { color-scheme: dark; }
body { font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Noto Sans SC',sans-serif; background:#121212; color:#e0e0e0; margin:0; min-width:900px; }
.app-container { max-width:1100px; margin:0 auto; padding:24px 32px; }
.top-bar { display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; }
.top-bar-left .logo { font-size:24px; font-weight:700; color:#409eff; }
.top-bar-left .version { font-size:12px; color:#666; font-weight:400; margin-left:8px; }

.status-dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:6px; }
.dot-idle { background:#666; }
.dot-running { background:#18a058; animation:pulse 1.5s ease-in-out infinite; }
.dot-completed { background:#409eff; }
.dot-error { background:#d03050; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.3} }

.control-panel { display:flex; align-items:center; gap:32px; margin-bottom:24px; padding:16px 20px; background:#1E1E1E; border-radius:8px; }
.button-group { display:flex; gap:12px; flex-shrink:0; }
.stats-row { display:flex; gap:16px; flex:1; justify-content:flex-end; }
.stat-card { text-align:center; padding:8px 16px; border-radius:6px; background:#2A2A2A; min-width:70px; }
.stat-number { font-size:22px; font-weight:700; }
.stat-label { font-size:11px; color:#999; margin-top:2px; }
.stat-high .stat-number { color:#18a058; } .stat-medium .stat-number { color:#409eff; }
.stat-try .stat-number { color:#f0a020; } .stat-total .stat-number { color:#fff; }

.jobs-section { min-height:300px; }
.job-cards { display:flex; flex-direction:column; gap:12px; }
.job-card { background:#1E1E1E; border-radius:8px; padding:16px 20px; }
.jc-header { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }
.jc-title { font-size:16px; font-weight:600; }
.jc-meta { display:flex; gap:16px; font-size:13px; color:#aaa; margin-bottom:8px; }
.jc-salary { color:#f0a020; }
.jc-reason { font-size:13px; color:#bbb; margin-bottom:6px; line-height:1.5; }
.jc-greeting { font-size:12px; color:#888; margin-bottom:8px; background:#252525; padding:6px 10px; border-radius:4px; }
.jc-actions { display:flex; gap:8px; }

.notif-bar { position:fixed; bottom:20px; left:50%; transform:translateX(-50%); z-index:100; min-width:400px; }
</style>
