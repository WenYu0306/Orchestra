<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'

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
// 步骤 3：DeepSeek Key
const keyConfigured = ref(false)
const keyInput = ref('')
const keyState = ref({ status: 'idle', message: '', balance: null }) // idle|checking|valid|invalid
// 步骤 4：城市 + 期望薪资
const allCities = ref([])
const selNames = ref([])
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
    case 4: return selNames.value.length > 0 && !savingCities.value
    default: return false
  }
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
      selNames.value = (r.cities || []).map(c => c.name)
      const mins = (r.cities || []).map(c => c.min_salary).filter(Boolean)
      if (mins.length) minSalary.value = Math.max(1, Math.round(Math.min(...mins) / 1000))
    }
  } catch (e) { /* 后端不可达：各步操作会给出明确报错 */ }
})

function onKeyInput() {
  if (keyState.value.status !== 'idle') keyState.value = { status: 'idle', message: '', balance: null }
}

async function handleFile(rawFile) {
  if (!rawFile.name.toLowerCase().endsWith('.pdf')) {
    ElMessage.error('请上传 PDF 格式的简历')
    return false
  }
  uploading.value = true
  try {
    const fd = new FormData()
    fd.append('file', rawFile)
    const r = await fetch('/api/upload-resume', { method: 'POST', body: fd })
    if (r.ok) {
      const d = await r.json()
      resumeUploaded.value = true
      resumeName.value = d.filename || rawFile.name
    } else {
      const d = await r.json().catch(() => ({}))
      ElMessage.error(d.detail || '上传失败，请重试')
    }
  } catch (err) {
    ElMessage.error('上传失败：' + (err.message || err))
  } finally {
    uploading.value = false
  }
  return false // 阻止 el-upload 默认上传
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
      keyState.value = { status: 'invalid', message: typeof d.detail === 'string' ? d.detail : '校验失败', balance: null }
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
          cities: selNames.value.map(name => ({
            name, min_salary: (parseInt(minSalary.value) || 8) * 1000,
          })),
        }),
      })
      if (!r.ok) { ElMessage.error('城市保存失败，请重试'); return }
    } catch (e) {
      ElMessage.error('保存失败：' + (e.message || e))
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
  <el-dialog :model-value="visible" width="760px" :show-close="false"
             :close-on-click-modal="false" :close-on-press-escape="false"
             class="wizard-dialog" style="--el-dialog-padding-primary: 24px;">
    <template #header>
      <div class="wiz-head">
        <div class="brand"><span class="mark">O</span><b>Orchestra</b></div>
        <el-steps :active="step - 1" finish-status="success" align-center
                  style="flex: 1; margin-left: 24px;">
          <el-step v-for="label in STEP_LABELS" :key="label" :title="label" />
        </el-steps>
      </div>
    </template>

    <!-- 步骤 1：欢迎 + 风险告知 -->
    <div v-if="step === 1" class="pane">
      <h2 class="pane-title">欢迎使用 Orchestra</h2>
      <p class="pane-sub">AI 求职助手：自动搜索岗位 → 按你的简历匹配打分 → 生成个性化招呼语 → 你确认后按真人节奏发送。</p>
      <el-alert type="warning" :closable="false">
        <template #title>开始前请了解</template>
        <ul class="risk-list">
          <li>本工具通过浏览器自动化操作<b>你本人登录</b>的 BOSS 直聘账号。平台用户协议通常限制自动化操作，<b>存在账号被限流/限制的可能</b>，请知悉并控制使用频率。</li>
          <li>工具默认按真人节奏运行（发送间隔 45~120 秒、每日上限 50 条、异常自动停止）。<b>请勿调低这些参数。</b></li>
          <li>所有数据（简历、投递记录、登录态）只保存在你的电脑上，本工具不上传任何数据。</li>
        </ul>
      </el-alert>
      <el-checkbox v-model="riskAgreed" style="margin-top: 14px">
        我已阅读并理解上述说明，愿意自担风险
      </el-checkbox>
    </div>

    <!-- 步骤 2：简历 -->
    <div v-else-if="step === 2" class="pane">
      <h2 class="pane-title">上传你的简历</h2>
      <p class="pane-sub">AI 用它来匹配岗位和生成招呼语，只保存在本机。</p>
      <el-upload drag accept=".pdf" :auto-upload="false" :show-file-list="false"
                 :on-change="f => handleFile(f.raw)">
        <template v-if="uploading">
          <div class="el-upload__text">上传中…</div>
        </template>
        <template v-else-if="resumeUploaded">
          <div class="el-upload__text">✅ 简历已就绪</div>
          <div class="el-upload__text" style="font-size:12px; color:#999">{{ resumeName || '点击可更换' }}</div>
        </template>
        <template v-else>
          <div class="el-upload__text">拖入 PDF 简历，或<em>点击选择文件</em></div>
        </template>
        <template #tip>
          <div class="el-upload__tip" v-if="!resumeUploaded && !uploading">文字版 PDF（扫描件/图片版无法识别）</div>
        </template>
      </el-upload>
    </div>

    <!-- 步骤 3：DeepSeek Key -->
    <div v-else-if="step === 3" class="pane">
      <h2 class="pane-title">连接 DeepSeek</h2>
      <p class="pane-sub">匹配打分和招呼语生成由 DeepSeek 驱动，需要你自己的 API Key（一次完整运行约花费几毛钱）。</p>
      <el-alert v-if="keyConfigured" type="success" :closable="false"
                title="DeepSeek 已配置。如需更换，在下方填入新 Key。" style="margin-bottom: 14px" />
      <div class="key-row">
        <el-input v-model="keyInput" type="password" show-password placeholder="sk-… 粘贴你的 DeepSeek API Key"
                  style="flex: 1" @input="onKeyInput" />
        <el-button type="primary" :disabled="!keyInput.trim() || keyState.status === 'checking'"
                   @click="verifyKey">{{ keyState.status === 'checking' ? '校验中…' : '验证' }}</el-button>
      </div>
      <el-alert v-if="keyState.message" :type="keyState.status === 'valid' ? 'success' : keyState.status === 'invalid' ? 'error' : 'info'"
                :title="keyState.message" :closable="false" style="margin-top: 12px" />
      <el-divider />
      <div class="guide">
        <b>没有 Key？三步搞定：</b>
        <ol class="guide-list">
          <li>打开 <a href="https://platform.deepseek.com" target="_blank" rel="noopener">platform.deepseek.com</a> 注册（手机号即可）</li>
          <li>充值 10 元，在「API Keys」页创建 Key</li>
          <li>粘贴到上面，点「验证」</li>
        </ol>
      </div>
    </div>

    <!-- 步骤 4：城市 + 期望薪资 -->
    <div v-else-if="step === 4" class="pane">
      <h2 class="pane-title">在哪里找工作？</h2>
      <p class="pane-sub">选择搜索范围并设置期望最低月薪。推荐直接选「全国」——一次搜遍所有城市。</p>
      <el-form label-position="top">
        <el-form-item label="搜索范围（可多选）">
          <el-select v-model="selNames" multiple filterable collapse-tags collapse-tags-tooltip
                     placeholder="搜索或选择城市" style="width: 100%">
            <el-option label="全国 · 一次搜遍所有城市（推荐）" value="全国" />
            <el-option v-for="c in allCities" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="期望最低月薪（K）">
          <el-input-number v-model="minSalary" :min="1" :max="100" />
          <span class="hint" style="margin-left: 8px">低于此值的岗位自动过滤</span>
        </el-form-item>
      </el-form>
    </div>

    <!-- 步骤 5：扫码登录 -->
    <div v-else-if="step === 5" class="pane">
      <template v-if="loginState !== 'success'">
        <h2 class="pane-title">登录 BOSS 直聘</h2>
        <p class="pane-sub">点击下方按钮会打开一个 Chrome 窗口，请用 BOSS 直聘 App 扫码登录。登录态保存在本机，之后基本不用再扫。</p>
        <el-button type="primary" size="large" style="width: 100%" :loading="loginState === 'starting'"
                   @click="startLogin">{{ loginState === 'starting' ? '请稍候…' : '打开浏览器，扫码登录' }}</el-button>
        <el-alert v-if="loginMsg" :type="loginState === 'fail' ? 'error' : 'info'" :title="loginMsg"
                  :closable="false" style="margin-top: 14px" />
        <div class="skip-row"><a class="skip-link" @click="finish(false)">跳过，先不登录（运行时再扫码）</a></div>
      </template>
      <template v-else>
        <el-result icon="success" title="一切就绪！"
                   sub-title="简历、Key、城市都已配置。AI 会自动搜索今天的岗位并打分，完成后你逐条确认发送。">
        </el-result>
        <el-alert type="info" :closable="false"
                  title="以后更新版本时：把旧目录的 data 文件夹和 .env 文件拷进新目录，配置、登录态、投递记录全部保留。"
                  style="margin-bottom: 16px" />
        <el-button type="primary" size="large" style="width: 100%" @click="finish(true)">开始第一次运行</el-button>
        <div class="skip-row"><a class="skip-link" @click="finish(false)">先不运行，看看界面</a></div>
      </template>
    </div>

    <template #footer>
      <div class="wiz-foot">
        <el-button v-if="step > 1 && step < 5" size="large" @click="prev">上一步</el-button>
        <span v-else class="foot-space"></span>
        <el-button v-if="step < 5" type="primary" size="large" :disabled="!canNext" @click="next">下一步</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<style scoped>
.wiz-head { display: flex; align-items: center; gap: 10px; }
.brand { display: flex; align-items: center; gap: 8px; }
.mark {
  width: 30px; height: 30px; border-radius: 8px;
  background: #409eff; color: #fff;
  display: grid; place-items: center; font-weight: 700;
}
.pane { min-height: 280px; }
.pane-title { margin: 0 0 8px; font-size: 18px; font-weight: 700; }
.pane-sub { margin: 0 0 18px; font-size: 14px; line-height: 1.6; color: var(--el-text-color-regular); }
.risk-list { margin: 6px 0 0; padding-left: 18px; font-size: 13px; line-height: 1.7; }
.key-row { display: flex; gap: 10px; }
.guide { font-size: 14px; color: var(--el-text-color-regular); }
.guide-list { margin: 8px 0 0; padding-left: 18px; line-height: 1.8; }
.hint { font-size: 12px; color: var(--el-text-color-secondary); }
.skip-row { text-align: center; margin-top: 14px; }
.skip-link { font-size: 12px; color: var(--el-text-color-secondary); cursor: pointer; text-decoration: underline; }
.wiz-foot { display: flex; justify-content: space-between; }
.foot-space { flex: 1; }
.done-box { padding: 4px 0; }
</style>
