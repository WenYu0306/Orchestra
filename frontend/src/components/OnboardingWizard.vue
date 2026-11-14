<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'

const props = defineProps({ visible: Boolean })
const emit = defineEmits(['done'])

const STEP_LABELS = ['欢迎', '简历', 'API Key', '城市', '登录']
const POPULAR = ['北京', '上海', '广州', '深圳', '杭州', '成都', '武汉', '南京',
                 '西安', '苏州', '长沙', '重庆', '天津', '合肥', '郑州', '青岛']

const step = ref(1)
// 步骤 1：风险告知
const riskAgreed = ref(false)
// 步骤 2：简历
const resumeUploaded = ref(false)
const resumeName = ref('')
const uploading = ref(false)
const dragOver = ref(false)
// 步骤 3：DeepSeek Key
const keyConfigured = ref(false)
const keyInput = ref('')
const keyState = ref({ status: 'idle', message: '', balance: null }) // idle|checking|valid|invalid
// 步骤 4：城市 + 期望薪资
const allCities = ref([])
const selected = ref(new Set())
const citySearch = ref('')
const minSalary = ref(8) // 单位 K
const savingCities = ref(false)
// 步骤 5：扫码登录
const loginState = ref('idle') // idle|starting|success|fail
const loginMsg = ref('')
let sse = null

const canNext = computed(() => {
  switch (step.value) {
    case 1: return riskAgreed.value
    case 2: return resumeUploaded.value
    case 3: return keyConfigured.value || keyState.value.status === 'valid'
    case 4: return selected.value.size > 0 && !savingCities.value
    default: return false
  }
})

const popularCities = computed(() => POPULAR.filter(c => allCities.value.includes(c)))
const otherCities = computed(() => {
  const q = citySearch.value.trim()
  return allCities.value.filter(c => !POPULAR.includes(c) && (!q || c.includes(q)))
})

onMounted(async () => {
  try {
    const r = await (await fetch('/api/settings')).json()
    keyConfigured.value = !!r.key_configured
    resumeUploaded.value = !!r.resume_uploaded
    allCities.value = r.supported_cities || []
    // 仅完成过向导的用户回填已有城市——全新买家不预选（决策：城市步不默认勾选，
    // config.yaml 的 example 默认城市不该悄悄替买家做主）
    if (r.wizard_done) {
      for (const c of (r.cities || [])) selected.value.add(c.name)
      const mins = (r.cities || []).map(c => c.min_salary).filter(Boolean)
      if (mins.length) minSalary.value = Math.max(1, Math.round(Math.min(...mins) / 1000))
    }
  } catch (e) { /* 后端不可达：各步操作会给出明确报错 */ }
})

function toggleCity(name) {
  const s = new Set(selected.value)
  if (s.has(name)) s.delete(name)
  else s.add(name)
  selected.value = s
}

function onKeyInput() {
  if (keyState.value.status !== 'idle') keyState.value = { status: 'idle', message: '', balance: null }
}

async function handleFile(e) {
  const f = e.target.files?.[0] || e.dataTransfer?.files?.[0]
  if (!f) return
  if (!f.name.toLowerCase().endsWith('.pdf')) {
    alert('请上传 PDF 格式的简历')
    return
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', f)
    const r = await fetch('/api/upload-resume', { method: 'POST', body: fd })
    if (r.ok) {
      const d = await r.json()
      resumeUploaded.value = true
      resumeName.value = d.filename || f.name
    } else {
      alert('上传失败，请重试')
    }
  } catch (err) {
    alert('上传失败：' + (err.message || err))
  } finally {
    uploading.value = false
    dragOver.value = false
  }
}

async function verifyKey() {
  const k = keyInput.value.trim()
  if (!k) return
  keyState.value = { status: 'checking', message: '校验中…', balance: null }
  try {
    const r = await fetch('/api/verify-key', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ key: k }),
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok) {
      keyState.value = { status: 'invalid', message: d.detail || '校验失败', balance: null }
      return
    }
    keyState.value = { status: d.valid ? 'valid' : 'invalid', message: d.message || '', balance: d.balance }
  } catch (e) {
    keyState.value = { status: 'invalid', message: '网络异常：' + (e.message || e), balance: null }
  }
}

async function next() {
  if (!canNext.value) return
  if (step.value === 3 && !keyConfigured.value) {
    try {
      const r = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ deepseek_key: keyInput.value.trim() }),
      })
      if (!r.ok) {
        const d = await r.json().catch(() => ({}))
        keyState.value = { status: 'invalid', message: d.message || d.detail || '保存失败', balance: null }
        return
      }
      keyConfigured.value = true
    } catch (e) {
      keyState.value = { status: 'invalid', message: '保存失败：' + (e.message || e), balance: null }
      return
    }
  }
  if (step.value === 4) {
    savingCities.value = true
    try {
      const r = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          cities: [...selected.value].map(name => ({
            name, min_salary: (parseInt(minSalary.value) || 8) * 1000,
          })),
        }),
      })
      if (!r.ok) { alert('城市保存失败，请重试'); return }
    } catch (e) {
      alert('保存失败：' + (e.message || e))
      return
    } finally {
      savingCities.value = false
    }
  }
  step.value = Math.min(step.value + 1, 5)
}

function prev() { step.value = Math.max(step.value - 1, 1) }

function startLogin() {
  loginState.value = 'starting'
  loginMsg.value = '正在启动浏览器…'
  sse = new EventSource('/api/events')
  sse.addEventListener('status', e => {
    try { const d = JSON.parse(e.data); if (d.message) loginMsg.value = d.message } catch { /* 忽略非 JSON */ }
  })
  sse.addEventListener('error', e => {
    if (e.data) {
      try { const d = JSON.parse(e.data); if (d.message) loginMsg.value = d.message } catch { /* 忽略 */ }
    }
  })
  fetch('/api/login', { method: 'POST' }).then(async r => {
    const d = await r.json().catch(() => ({}))
    if (r.ok && d.success) {
      loginState.value = 'success'
      loginMsg.value = '登录成功，登录态已保存在本机'
    } else {
      loginState.value = 'fail'
      loginMsg.value = d.detail || d.message || '登录未完成'
    }
    closeSse()
  }).catch(e => {
    loginState.value = 'fail'
    loginMsg.value = '请求失败：' + (e.message || e)
    closeSse()
  })
}

function closeSse() { if (sse) { sse.close(); sse = null } }

async function finish(startRun) {
  closeSse()
  try {
    await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ wizard_done: true }),
    })
  } catch (e) { /* 标记失败不阻塞：下次启动会再进向导 */ }
  emit('done', { startRun })
}

onUnmounted(closeSse)
</script>

<template>
  <Transition name="wizard-fade">
    <div v-if="visible" class="wizard-mask">
      <div class="wizard">
        <!-- 步骤指示器 -->
        <header class="wiz-head">
          <div class="wiz-logo">
            <div class="logo-mark">
              <span class="bar" style="height:10px;top:11px;left:8px"></span>
              <span class="bar" style="height:18px;top:7px;left:12.5px"></span>
              <span class="bar" style="height:6px;top:13px;left:17px"></span>
              <span class="bar" style="height:14px;top:9px;left:21.5px"></span>
            </div>
            <span class="logo-text">Orchestra</span>
          </div>
          <div class="steps">
            <div v-for="(label, i) in STEP_LABELS" :key="label" class="step-dot"
                 :class="{ active: step === i + 1, passed: step > i + 1 }">
              <span class="dot">{{ step > i + 1 ? '✓' : i + 1 }}</span>
              <span class="label">{{ label }}</span>
            </div>
          </div>
        </header>

        <main class="wiz-body">
          <!-- 步骤 1：欢迎 + 风险告知 -->
          <section v-if="step === 1" class="step-pane">
            <h2 class="pane-title">欢迎使用 Orchestra</h2>
            <p class="pane-sub">AI 求职助手：自动搜索岗位 → 按你的简历匹配打分 → 生成个性化招呼语 → 你确认后按真人节奏发送。</p>
            <div class="risk-box">
              <div class="risk-title">开始前请了解</div>
              <ul class="risk-list">
                <li>本工具通过浏览器自动化操作<b>你本人登录</b>的 BOSS 直聘账号。平台用户协议通常限制自动化操作，<b>存在账号被限流/限制的可能</b>，请知悉并控制使用频率。</li>
                <li>工具默认按真人节奏运行（发送间隔 45~120 秒、每日上限 50 条、异常自动停止）。<b>请勿调低这些参数。</b></li>
                <li>所有数据（简历、投递记录、登录态）只保存在你的电脑上，本工具不上传任何数据。</li>
              </ul>
              <label class="agree-row">
                <input type="checkbox" v-model="riskAgreed" />
                <span>我已阅读并理解上述说明，愿意自担风险</span>
              </label>
            </div>
          </section>

          <!-- 步骤 2：简历 -->
          <section v-else-if="step === 2" class="step-pane">
            <h2 class="pane-title">上传你的简历</h2>
            <p class="pane-sub">AI 用它来匹配岗位和生成招呼语，只保存在本机。</p>
            <label class="dropzone" :class="{ over: dragOver, done: resumeUploaded }"
                   @dragover.prevent="dragOver = true"
                   @dragleave.prevent="dragOver = false"
                   @drop.prevent="handleFile">
              <input type="file" accept=".pdf" style="display:none" @change="handleFile" />
              <template v-if="uploading">上传中…</template>
              <template v-else-if="resumeUploaded">
                <span class="dz-check">✓</span>
                <span class="dz-name">{{ resumeName || '简历已就绪' }}</span>
                <span class="dz-hint">点击可更换</span>
              </template>
              <template v-else>
                <span class="dz-icon">📄</span>
                <span>拖入 PDF 简历，或点击选择文件</span>
              </template>
            </label>
          </section>

          <!-- 步骤 3：DeepSeek Key -->
          <section v-else-if="step === 3" class="step-pane">
            <h2 class="pane-title">连接 DeepSeek</h2>
            <p class="pane-sub">匹配打分和招呼语生成由 DeepSeek 驱动，需要你自己的 API Key（一次完整运行约花费几毛钱）。</p>
            <div v-if="keyConfigured" class="key-ok">
              ✓ DeepSeek 已配置。如需更换，在下方填入新 Key。
            </div>
            <div class="key-row">
              <input class="text-input" type="password" v-model="keyInput"
                     placeholder="sk-… 粘贴你的 DeepSeek API Key" @input="onKeyInput" />
              <button class="verify-btn" :disabled="!keyInput.trim() || keyState.status === 'checking'"
                      @click="verifyKey">
                {{ keyState.status === 'checking' ? '校验中…' : '验证' }}
              </button>
            </div>
            <p v-if="keyState.message" class="key-state" :class="keyState.status">
              {{ keyState.status === 'checking' ? '⏳' : keyState.status === 'valid' ? '✓' : '✕' }}
              {{ keyState.message }}
            </p>
            <div class="key-guide">
              <div class="guide-title">没有 Key？三步搞定：</div>
              <ol class="guide-list">
                <li>打开 <a href="https://platform.deepseek.com" target="_blank" rel="noopener">platform.deepseek.com</a> 注册（手机号即可）</li>
                <li>充值 10 元，在「API Keys」页创建 Key</li>
                <li>粘贴到上面，点「验证」</li>
              </ol>
            </div>
          </section>

          <!-- 步骤 4：城市 + 期望薪资 -->
          <section v-else-if="step === 4" class="step-pane">
            <h2 class="pane-title">在哪里找工作？</h2>
            <p class="pane-sub">选择搜索城市（可多选），并设置期望最低月薪。</p>
            <div class="salary-row">
              <span class="salary-label">期望最低月薪</span>
              <input class="salary-input" type="number" min="1" max="100" v-model.number="minSalary" />
              <span class="salary-unit">K（低于此值的岗位自动过滤）</span>
            </div>
            <input class="text-input city-search" v-model="citySearch" placeholder="搜索城市…" />
            <div class="city-group">
              <div class="group-label">搜索范围</div>
              <div class="chips">
                <button class="chip nation-chip" :class="{ active: selected.has('全国') }"
                        @click="toggleCity('全国')">全国 · 一次搜遍所有城市（推荐）</button>
              </div>
            </div>
            <div class="city-group" v-if="popularCities.length">
              <div class="group-label">热门城市</div>
              <div class="chips">
                <button v-for="c in popularCities" :key="c" class="chip"
                        :class="{ active: selected.has(c) }" @click="toggleCity(c)">{{ c }}</button>
              </div>
            </div>
            <div class="city-group">
              <div class="group-label">全部城市（{{ otherCities.length }}）</div>
              <div class="chips">
                <button v-for="c in otherCities" :key="c" class="chip"
                        :class="{ active: selected.has(c) }" @click="toggleCity(c)">{{ c }}</button>
              </div>
            </div>
          </section>

          <!-- 步骤 5：扫码登录 -->
          <section v-else-if="step === 5" class="step-pane">
            <template v-if="loginState !== 'success'">
              <h2 class="pane-title">登录 BOSS 直聘</h2>
              <p class="pane-sub">点击下方按钮会打开一个 Chrome 窗口，请用 BOSS 直聘 App 扫码登录。登录态保存在本机，之后基本不用再扫。</p>
              <button class="login-btn" :disabled="loginState === 'starting'" @click="startLogin">
                {{ loginState === 'starting' ? '请稍候…' : '打开浏览器，扫码登录' }}
              </button>
              <p v-if="loginMsg" class="login-msg" :class="{ fail: loginState === 'fail' }">{{ loginMsg }}</p>
              <a class="skip-link" @click="finish(false)">跳过，先不登录（运行时再扫码）</a>
            </template>
            <template v-else>
              <div class="done-emoji">🎉</div>
              <h2 class="pane-title">一切就绪！</h2>
              <p class="pane-sub">简历、Key、城市都已配置。点「开始」，AI 会自动搜索今天的岗位并打分，完成后你逐条确认发送。</p>
              <p class="pane-sub migrate-hint">以后更新版本时：把旧目录的 <b>data 文件夹</b>和 <b>.env 文件</b>拷进新目录，配置、登录态、投递记录全部保留。</p>
              <button class="start-run-btn" @click="finish(true)">开始第一次运行</button>
              <a class="skip-link" @click="finish(false)">先不运行，看看界面</a>
            </template>
          </section>
        </main>

        <footer class="wiz-foot">
          <button v-if="step > 1 && step < 5" class="ghost-btn" @click="prev">上一步</button>
          <span v-else class="foot-space"></span>
          <button v-if="step < 5" class="next-btn" :disabled="!canNext" @click="next">下一步</button>
        </footer>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.wizard-mask {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(15, 18, 34, 0.45);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  display: flex; align-items: center; justify-content: center;
  padding: 24px;
}
.wizard {
  width: 680px; max-width: 100%; max-height: 92vh;
  display: flex; flex-direction: column;
  background: rgba(255, 255, 255, 0.96);
  border: 1px solid rgba(255, 255, 255, 0.6);
  border-radius: 24px;
  box-shadow: 0 24px 64px rgba(15, 18, 34, 0.25);
  overflow: hidden;
}
.wiz-head {
  display: flex; align-items: center; justify-content: space-between;
  padding: 20px 28px 14px;
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
}
.wiz-logo { display: flex; align-items: center; gap: 10px; }
.logo-mark {
  position: relative; width: 30px; height: 30px; border-radius: 8px;
  background: linear-gradient(135deg, #A78BFA 0%, #7DD3FC 100%);
}
.logo-mark .bar { position: absolute; width: 2.5px; background: #fff; border-radius: 1px; }
.logo-text { font-family: 'Geist', sans-serif; font-weight: 600; font-size: 16px; color: var(--text-1); }
.steps { display: flex; gap: 14px; }
.step-dot { display: flex; align-items: center; gap: 6px; }
.step-dot .dot {
  width: 22px; height: 22px; border-radius: 999px;
  display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600;
  background: #f1f5f9; color: #94a3b8;
  transition: all .2s;
}
.step-dot.active .dot { background: #6366f1; color: #fff; }
.step-dot.passed .dot { background: rgba(99, 102, 241, 0.12); color: #6366f1; }
.step-dot .label { font-size: 11px; color: #94a3b8; }
.step-dot.active .label { color: var(--text-1, #1e293b); font-weight: 600; }
.wiz-body { flex: 1; overflow-y: auto; padding: 28px 32px; }
.wiz-foot {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 28px 20px;
  border-top: 1px solid rgba(148, 163, 184, 0.15);
}
.foot-space { flex: 1; }

.pane-title { margin: 0 0 6px; font-size: 20px; font-weight: 700; color: var(--text-1, #1e293b); }
.pane-sub { margin: 0 0 20px; font-size: 13px; line-height: 1.6; color: var(--text-2, #64748b); }

/* 步骤 1 */
.risk-box {
  background: #fffbeb; border: 1px solid #fde68a; border-radius: 14px;
  padding: 16px 18px;
}
.risk-title { font-size: 13px; font-weight: 700; color: #92400e; margin-bottom: 10px; }
.risk-list { margin: 0; padding-left: 18px; font-size: 12.5px; line-height: 1.7; color: #78350f; }
.risk-list b { color: #92400e; }
.agree-row {
  display: flex; align-items: center; gap: 8px; margin-top: 12px;
  font-size: 12.5px; color: #78350f; cursor: pointer; user-select: none;
}
.agree-row input { accent-color: #6366f1; }

/* 步骤 2 */
.dropzone {
  display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 8px;
  min-height: 180px; border-radius: 16px; cursor: pointer;
  border: 2px dashed #e0e5ea; background: #f8fafc;
  font-size: 13px; color: var(--text-2, #64748b);
  transition: all .2s;
}
.dropzone.over { border-color: #6366f1; background: rgba(99, 102, 241, 0.05); }
.dropzone.done { border-style: solid; border-color: rgba(16, 185, 129, 0.5); background: #f0fdf4; }
.dz-icon { font-size: 28px; }
.dz-check {
  width: 34px; height: 34px; border-radius: 999px;
  background: #10b981; color: #fff;
  display: flex; align-items: center; justify-content: center; font-size: 16px; font-weight: 700;
}
.dz-name { font-weight: 600; color: var(--text-1, #1e293b); }
.dz-hint { font-size: 11px; color: #94a3b8; }

/* 步骤 3 */
.key-ok {
  padding: 10px 14px; border-radius: 10px; margin-bottom: 14px;
  background: #f0fdf4; border: 1px solid rgba(16, 185, 129, 0.35);
  color: #047857; font-size: 12.5px;
}
.key-row { display: flex; gap: 10px; }
.text-input {
  flex: 1; height: 40px; padding: 0 12px;
  border: 1px solid #e0e5ea; border-radius: 10px;
  font-size: 13px; color: var(--text-1, #1e293b); outline: none;
  font-family: 'Geist Mono', monospace;
}
.text-input:focus { border-color: #6366f1; }
.verify-btn {
  height: 40px; padding: 0 18px; border: none; border-radius: 10px;
  background: #6366f1; color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
}
.verify-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.key-state { margin: 10px 0 0; font-size: 12.5px; }
.key-state.valid { color: #047857; }
.key-state.invalid { color: #dc2626; }
.key-state.checking { color: var(--text-2, #64748b); }
.key-guide {
  margin-top: 18px; padding: 14px 16px;
  background: #f8fafc; border-radius: 12px; border: 1px solid #eef2f6;
}
.guide-title { font-size: 12px; font-weight: 600; color: var(--text-2, #64748b); margin-bottom: 6px; }
.guide-list { margin: 0; padding-left: 18px; font-size: 12.5px; line-height: 1.8; color: var(--text-2, #64748b); }
.guide-list a { color: #6366f1; }

/* 步骤 4 */
.salary-row {
  display: flex; align-items: center; gap: 8px; margin-bottom: 16px;
  font-size: 13px; color: var(--text-2, #64748b);
}
.salary-input {
  width: 64px; height: 34px; text-align: center;
  border: 1px solid #e0e5ea; border-radius: 8px;
  font-size: 14px; font-weight: 600; color: var(--text-1, #1e293b); outline: none;
  font-family: 'Geist Mono', monospace;
}
.salary-input:focus { border-color: #6366f1; }
.city-search { width: 100%; margin-bottom: 14px; font-family: inherit; }
.city-group { margin-bottom: 14px; }
.group-label { font-size: 11.5px; font-weight: 600; color: #94a3b8; margin-bottom: 8px; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  padding: 7px 14px; font-size: 12.5px; font-weight: 500;
  border-radius: 999px; cursor: pointer;
  border: 1px solid #e0e5ea; background: #ffffff; color: #64748b;
  transition: all .15s;
}
.chip.active { background: #6366f1; border-color: #6366f1; color: #fff; font-weight: 600; }
.nation-chip {
  border-color: rgba(99, 102, 241, 0.5);
  background: rgba(99, 102, 241, 0.08);
  color: #4f46e5;
  font-weight: 600;
}
.nation-chip.active { background: #6366f1; color: #fff; }

/* 步骤 5 */
.login-btn, .start-run-btn {
  width: 100%; height: 46px; border: none; border-radius: 12px;
  background: #6366f1; color: #fff; font-size: 14px; font-weight: 600; cursor: pointer;
  transition: background .15s;
}
.login-btn:hover, .start-run-btn:hover { background: #4f46e5; }
.login-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.login-msg { margin: 14px 0 0; text-align: center; font-size: 13px; color: var(--text-2, #64748b); }
.login-msg.fail { color: #dc2626; }
.skip-link {
  display: block; margin-top: 12px; text-align: center;
  font-size: 12px; color: #94a3b8; cursor: pointer; text-decoration: underline;
}
.done-emoji { text-align: center; font-size: 40px; margin: 8px 0 4px; }

/* 底部按钮 */
.ghost-btn {
  height: 40px; padding: 0 18px; border-radius: 10px; cursor: pointer;
  border: 1px solid #e0e5ea; background: #fff; color: var(--text-2, #64748b);
  font-size: 13px;
}
.next-btn {
  height: 40px; padding: 0 28px; border: none; border-radius: 10px;
  background: #6366f1; color: #fff; font-size: 13px; font-weight: 600; cursor: pointer;
}
.next-btn:disabled { opacity: 0.45; cursor: not-allowed; }

.wizard-fade-enter-active, .wizard-fade-leave-active { transition: opacity .3s ease; }
.wizard-fade-enter-from, .wizard-fade-leave-to { opacity: 0; }

@media (max-width: 720px) {
  .steps .label { display: none; }
  .wiz-body { padding: 20px; }
}
</style>
