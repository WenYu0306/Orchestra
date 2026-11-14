<script setup>
import { ref, watch } from 'vue'

const props = defineProps({ visible: Boolean })
const emit = defineEmits(['close', 'save'])

const keyInput = ref('')
const keyState = ref({ configured: false, tail: '' })
const cities = ref([])
const minSalary = ref(8) // 全局期望最低月薪（K）——不再逐城设置
const busy = ref(false)
const error = ref('')

watch(() => props.visible, async (v) => {
  if (!v) return
  error.value = ''
  keyInput.value = ''
  try {
    const r = await (await fetch('/api/settings')).json()
    keyState.value = { configured: !!r.key_configured, tail: r.key_tail || '' }
    const sel = new Map((r.cities || []).map(c => [c.name, c.min_salary]))
    cities.value = (r.supported_cities || []).map(name => ({
      name,
      selected: sel.has(name),
    }))
    const mins = (r.cities || []).map(c => c.min_salary).filter(Boolean)
    if (mins.length) minSalary.value = Math.max(1, Math.round(Math.min(...mins) / 1000))
    if (!cities.value.some(c => c.selected) && cities.value.length) {
      cities.value.slice(0, 2).forEach(c => { c.selected = true })
    }
  } catch (e) {
    error.value = '设置读取失败：后端不可达'
  }
})

function toggleCity(c) { c.selected = !c.selected }

async function save() {
  const sel = cities.value.filter(c => c.selected)
  if (!sel.length) { error.value = '请至少选择一个搜索城市'; return }
  busy.value = true; error.value = ''
  try {
    const r = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        deepseek_key: keyInput.value.trim(),
        cities: sel.map(c => ({ name: c.name, min_salary: (parseInt(minSalary.value) || 8) * 1000 })),
      }),
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok || d.ok === false) {
      error.value = d.message || d.detail || '保存失败'
      return
    }
    emit('save', { cities: sel.map(c => c.name) })
  } catch (e) {
    error.value = '保存失败：' + (e.message || e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <Transition name="drawer">
    <aside v-if="visible" class="drawer">
      <header class="head">
        <div class="title-group">
          <h2 class="title">设置</h2>
          <p class="subtitle">填好 Key 和搜索条件即可开始</p>
        </div>
        <button class="close-btn" aria-label="关闭" @click="emit('close')">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
            <path d="M6 6l12 12M18 6L6 18" stroke="#64748B" stroke-width="2.2" stroke-linecap="round"/>
          </svg>
        </button>
      </header>

      <section class="section">
        <label class="section-label">DeepSeek API Key</label>
        <input class="text-input" type="password" v-model="keyInput"
               :placeholder="keyState.configured
                 ? `已配置（尾号 ${keyState.tail}），留空则不修改`
                 : 'sk-… 填入后即可使用'" />
        <p class="hint">申请：platform.deepseek.com（充值 10 元可用很久）。Key 只保存在本机 .env。</p>
      </section>

      <section class="section">
        <label class="section-label">搜索城市 · 可多选</label>
        <div class="salary-row">
          <span class="salary-label">期望最低月薪</span>
          <input class="salary-input" type="number" min="1" max="100" v-model.number="minSalary" />
          <span class="salary-unit">K（低于此值的岗位自动过滤）</span>
        </div>
        <div class="chips">
          <button v-for="c in cities" :key="c.name" class="chip" :class="{ active: c.selected }"
                  @click="toggleCity(c)">
            {{ c.name }}
          </button>
        </div>
        <p class="hint">搜索关键词由 AI 根据你的简历自动生成，无需手动填写。</p>
      </section>

      <p v-if="error" class="error">{{ error }}</p>

      <div class="actions">
        <button class="apply-btn" :disabled="busy" @click="save">{{ busy ? '保存中…' : '保存设置' }}</button>
      </div>
    </aside>
  </Transition>
</template>

<style scoped>
.drawer {
  position: fixed;
  top: 0;
  right: 0;
  width: 440px;
  max-width: 92vw;
  height: 100vh;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 20px;
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(255, 255, 255, 0.5);
  border-radius: 20px 0 0 20px;
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.12);
  box-sizing: border-box;
  z-index: 50;
  overflow-y: auto;
}
.drawer-enter-active,
.drawer-leave-active {
  transition: transform 0.3s ease;
}
.drawer-enter-from,
.drawer-leave-to {
  transform: translateX(100%);
}
.head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.title-group { display: flex; flex-direction: column; gap: 3px; }
.title { margin: 0; font-family: 'Geist', sans-serif; font-size: 16px; font-weight: 600; color: #1e293b; }
.subtitle { margin: 0; font-size: 11.5px; color: #94a3b8; }
.close-btn {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: #f1f5f9; border: none; border-radius: 10px; cursor: pointer;
}
.section { display: flex; flex-direction: column; gap: 10px; }
.section-label { font-size: 12px; font-weight: 500; color: #475569; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
.chip {
  padding: 7px 13px;
  font-size: 12.5px;
  font-weight: 500;
  border-radius: 999px;
  cursor: pointer;
  border: 1px solid #e0e5ea;
  background: #ffffff;
  color: #64748b;
  transition: all 0.15s;
}
.chip.active {
  background: #6366f1;
  border-color: #6366f1;
  color: #ffffff;
  font-weight: 600;
}
.salary-row {
  display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
  font-size: 12px; color: #64748b;
}
.salary-input {
  width: 56px; height: 30px; text-align: center;
  border: 1px solid #e0e5ea; border-radius: 8px;
  font-size: 13px; font-weight: 600; color: #1e293b; outline: none;
  font-family: 'Geist Mono', monospace;
}
.salary-input:focus { border-color: #6366f1; }
.text-input {
  height: 38px;
  padding: 0 12px;
  border: 1px solid #e0e5ea;
  border-radius: 10px;
  font-size: 13px;
  color: #1e293b;
  outline: none;
  font-family: 'Geist Mono', monospace;
}
.text-input:focus { border-color: #6366f1; }
.hint { margin: 0; font-size: 11px; color: #94a3b8; line-height: 16px; }
.error {
  margin: 0;
  font-size: 12px;
  color: #dc2626;
  background: #fef2f2;
  border: 1px solid #fecaca;
  border-radius: 8px;
  padding: 8px 10px;
}
.actions { margin-top: auto; }
.apply-btn {
  width: 100%;
  height: 42px;
  background: #6366f1;
  color: #ffffff;
  font-size: 14px;
  font-weight: 600;
  border: none;
  border-radius: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.apply-btn:hover { background: #4f46e5; }
.apply-btn:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
