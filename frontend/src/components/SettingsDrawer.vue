<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({ visible: Boolean })
const emit = defineEmits(['close', 'save'])

const keyInput = ref('')
const keyState = ref({ configured: false, tail: '' })
const resumeUploaded = ref(false)
const uploading = ref(false)

async function uploadResume(rawFile) {
  uploading.value = true
  try {
    const fd = new FormData(); fd.append('file', rawFile)
    const r = await fetch('/api/upload-resume', { method: 'POST', body: fd })
    if (r.ok) { resumeUploaded.value = true; ElMessage.success('简历已更新') }
    else {
      const d = await r.json().catch(() => ({}))
      ElMessage.error(d.detail || '上传失败')
    }
  } catch (e) {
    ElMessage.error('上传失败：' + (e.message || e))
  } finally {
    uploading.value = false
  }
}
const cities = ref([])
const selNames = ref([])
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
    resumeUploaded.value = !!r.resume_uploaded
    const sel = new Set((r.cities || []).map(c => c.name))
    cities.value = r.supported_cities || []
    selNames.value = (r.cities || []).map(c => c.name)
    const mins = (r.cities || []).map(c => c.min_salary).filter(Boolean)
    if (mins.length) minSalary.value = Math.max(1, Math.round(Math.min(...mins) / 1000))
  } catch (e) {
    error.value = '设置读取失败：后端不可达'
  }
})

async function save() {
  if (!selNames.value.length) { error.value = '请至少选择一个搜索城市'; return }
  busy.value = true; error.value = ''
  try {
    const r = await fetch('/api/settings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        deepseek_key: keyInput.value.trim(),
        cities: selNames.value.map(name => ({ name, min_salary: (parseInt(minSalary.value) || 8) * 1000 })),
      }),
    })
    const d = await r.json().catch(() => ({}))
    if (!r.ok || d.ok === false) {
      error.value = d.message || d.detail || '保存失败'
      return
    }
    emit('save', { cities: selNames.value })
  } catch (e) {
    error.value = '保存失败：' + (e.message || e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <el-drawer :model-value="visible" title="设置" size="440px" @close="emit('close')">
    <el-form label-position="top" @submit.prevent>
      <el-form-item label="简历">
        <div class="resume-row">
          <el-tag :type="resumeUploaded ? 'success' : 'info'" effect="light">
            {{ resumeUploaded ? '简历已就绪' : '尚未上传简历' }}
          </el-tag>
          <el-upload :show-file-list="false" accept=".pdf" :auto-upload="false"
                     :on-change="f => uploadResume(f.raw)" style="display: inline-block">
            <el-button :loading="uploading">{{ resumeUploaded ? '更换简历' : '上传简历' }}</el-button>
          </el-upload>
        </div>
      </el-form-item>

      <el-form-item label="DeepSeek API Key">
        <el-input v-model="keyInput" type="password" show-password
                  :placeholder="keyState.configured
                    ? `已配置（尾号 ${keyState.tail}），留空则不修改`
                    : 'sk-… 填入后即可使用'" />
      </el-form-item>

      <el-form-item label="期望最低月薪（K）">
        <el-input-number v-model="minSalary" :min="1" :max="100" />
      </el-form-item>

      <el-form-item label="搜索城市 · 可多选（支持全国）">
        <el-select v-model="selNames" multiple filterable collapse-tags collapse-tags-tooltip
                   placeholder="搜索或选择城市" style="width: 100%">
          <el-option v-for="c in cities" :key="c" :label="c" :value="c" />
        </el-select>
      </el-form-item>

      <el-alert v-if="error" :title="error" type="error" :closable="false" style="margin-bottom: 12px" />

      <el-button type="primary" :loading="busy" style="width: 100%" @click="save">保存设置</el-button>
    </el-form>
  </el-drawer>
</template>

<style scoped>
.resume-row { display: flex; align-items: center; gap: 12px; }
</style>
