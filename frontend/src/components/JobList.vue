<script setup>
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

const props = defineProps({ jobs: Array, loading: Boolean })
const emit = defineEmits(['send'])

const activeTab = ref('sendable')
const sendableJobs = computed(() => props.jobs.filter(j => j.status !== 'review_only'))
const belowJobs = computed(() => props.jobs.filter(j => j.status === 'review_only'))
const listJobs = computed(() => activeTab.value === 'sendable' ? sendableJobs.value : belowJobs.value)

// 主从式：左列选择 → 右详情
const selectedUid = ref(null)
function select(j) { selectedUid.value = j.uid }
const selectedJob = computed(() =>
  listJobs.value.find(j => j.uid === selectedUid.value) || listJobs.value[0] || null)

// 批量勾选（独立于详情选择）
const selectedUids = ref(new Set())
function togglePick(j, e) {
  const s = new Set(selectedUids.value)
  if (s.has(j.uid)) s.delete(j.uid); else s.add(j.uid)
  selectedUids.value = s
}
const batchCount = computed(() => selectedUids.value.size)
function sendBatch() { emit('send', props.jobs.filter(j => selectedUids.value.has(j.uid))) }
function sendOne() { if (selectedJob.value) emit('send', [selectedJob.value]) }

function copyGreeting(row) {
  navigator.clipboard?.writeText(row.greeting || '').then(
    () => ElMessage.success('招呼语已复制'),
    () => ElMessage.error('复制失败'),
  )
}
</script>

<template>
  <div class="md-wrap">
  <div class="md">
    <!-- 左列：扫读清单 -->
    <div class="master">
      <div class="tabs">
        <button class="tab" :class="{ active: activeTab === 'sendable' }" @click="activeTab = 'sendable'; selectedUid = null">
          可投递 <b>{{ sendableJobs.length }}</b>
        </button>
        <button class="tab" :class="{ active: activeTab === 'below' }" @click="activeTab = 'below'; selectedUid = null">
          低于投递线 <b>{{ belowJobs.length }}</b>
        </button>
      </div>

      <div class="rows" v-loading="loading">
        <template v-if="activeTab === 'sendable'">
          <div v-if="!sendableJobs.length && !loading" class="empty-state">
            <div class="empty-title">还没有匹配的岗位</div>
            <div class="empty-hint">点右上角「开始」，AI 会自动搜索、打分、写好招呼语</div>
          </div>
          <div v-for="j in sendableJobs" :key="j.uid" class="row"
               :class="{ active: selectedJob && selectedJob.uid === j.uid, picked: selectedUids.has(j.uid) }"
               @click="select(j)">
            <input type="checkbox" :checked="selectedUids.has(j.uid)" @click.stop="togglePick(j, $event)"
                   :aria-label="`勾选 ${j.company}`">
            <div class="row-score">{{ j.score }}</div>
            <div class="row-body">
              <div class="row-company">{{ j.company }}</div>
              <div class="row-meta">{{ j.title }}<template v-if="j.salary"> · {{ j.salary }}</template></div>
            </div>
          </div>
        </template>
        <template v-else>
          <div class="below-hint">低于 60 分不生成招呼语、不占发送额度——行情参考</div>
          <div v-for="j in belowJobs" :key="j.uid" class="row"
               :class="{ active: selectedJob && selectedJob.uid === j.uid }" @click="select(j)">
            <div class="row-score dim">{{ j.score }}</div>
            <div class="row-body">
              <div class="row-company">{{ j.company }}</div>
              <div class="row-meta">{{ j.title }}<template v-if="j.salary"> · {{ j.salary }}</template></div>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 右侧：决策详情 -->
    <div class="detail">
      <template v-if="selectedJob">
        <div class="d-head">
          <div class="d-score" :class="{ pass: selectedJob.score >= 80 }">{{ selectedJob.score }}</div>
          <div class="d-title">
            <div class="d-company">{{ selectedJob.company }}</div>
            <div class="d-position">{{ selectedJob.title }}</div>
            <div class="d-meta">
              {{ selectedJob.salary }} · {{ selectedJob.search_city }}
              <span class="tier-mark" :class="{ pass: selectedJob.tier === 'high' }">{{ selectedJob.tier === 'high' ? '高匹配' : '中匹配' }}</span>
              <span v-if="selectedJob._sent" class="tier-mark pass">已发送</span>
              <span v-else-if="selectedJob._sendFailed" class="tier-mark fail">发送失败</span>
            </div>
          </div>
        </div>

        <div class="d-section">
          <div class="d-label">AI 为什么推荐它</div>
          <div class="d-reason">{{ selectedJob.reason }}</div>
        </div>

        <div class="d-section" v-if="activeTab === 'sendable'">
          <div class="d-label">招呼语（发送前可编辑）
            <el-tag v-if="selectedJob.greetingIsDefault" size="small" type="warning" effect="light">默认文案 · 建议修改</el-tag>
          </div>
          <el-input v-model="selectedJob.greeting" type="textarea" :rows="4" resize="vertical" />
          <div class="d-actions">
            <el-button size="small" @click="copyGreeting(selectedJob)">复制</el-button>
            <div class="grow"></div>
            <el-button type="primary" data-cuelume-tap @click="sendOne">发送这条</el-button>
          </div>
        </div>
      </template>
      <div v-else class="empty-state">
        <div class="empty-title">还没有匹配的岗位</div>
        <div class="empty-hint">点右上角「开始」，AI 会按你的简历自动搜索、逐个打分、写好招呼语</div>
      </div>
    </div>
  </div>
  <div class="md-bottom">
    <span class="md-count">已勾选 {{ batchCount }} 条 · 点击行内方框批量勾选</span>
    <div class="grow"></div>
    <el-button type="primary" data-cuelume-tap :disabled="batchCount === 0" @click="sendBatch">发送选中 {{ batchCount }}</el-button>
  </div>
  </div>
</template>

<style scoped>
.md-wrap { display: flex; flex-direction: column; }
.md { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 18px; min-height: 420px; flex: 1; }
.md-bottom {
  position: sticky; bottom: 0;
  display: flex; align-items: center; gap: 10px;
  padding: 10px 4px 2px;
  background: color-mix(in oklab, #faf7f0 90%, transparent);
}
.md-count { font-size: 12px; color: var(--el-text-color-secondary); font-variant-numeric: tabular-nums; }
.grow { flex: 1; }

/* 左列 */
.tabs { display: flex; gap: 10px; padding-bottom: 8px; }
.tab {
  font-size: 14px; color: var(--el-text-color-secondary);
  background: none; border: none; border-bottom: 2px solid transparent;
  cursor: pointer; padding: 5px 2px; font-family: inherit;
}
.tab b { font-weight: 700; margin-left: 3px; }
.tab.active { color: var(--el-text-color-primary); border-bottom-color: #1a1a1a; }
.rows { display: flex; flex-direction: column; gap: 6px; }
.row {
  display: grid; grid-template-columns: 16px 44px minmax(0, 1fr);
  gap: 10px; padding: 9px 10px;
  background: #fff; border: 1px solid #eee7db; border-radius: 10px;
  cursor: pointer; align-items: center;
}
.row:hover { border-color: #d8cfbf; }
.row.active { border-color: #1a1a1a; background: #fbfaf5; }
.row.picked { border-color: #0d7a5f; }
.row input { width: 14px; height: 14px; accent-color: #0d7a5f; cursor: pointer; }
.row-score {
  font-size: 20px; font-weight: 800; text-align: center;
  font-variant-numeric: tabular-nums; color: var(--el-text-color-primary);
}
.row-score.dim { color: var(--el-text-color-secondary); }
.row-body { min-width: 0; }
.row-company { font-weight: 600; font-size: 14px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.row-meta { font-size: 12px; color: var(--el-text-color-secondary); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.below-hint { font-size: 12px; color: var(--el-text-color-secondary); padding-bottom: 4px; }

/* 右详情 */
.detail {
  background: #fff; border: 1px solid #eee7db; border-radius: 12px;
  padding: 18px 22px; align-self: start;
}
.d-head { display: flex; gap: 18px; align-items: center; padding-bottom: 14px; border-bottom: 1px solid #eee7db; }
.d-score {
  font-size: 56px; font-weight: 800; line-height: 0.95;
  font-variant-numeric: tabular-nums; letter-spacing: -0.03em;
  color: var(--el-text-color-primary);
}
.d-score.pass { color: #0d7a5f; }
.d-company { font-size: 17px; font-weight: 800; }
.d-position { font-size: 14px; color: var(--el-text-color-regular); margin-top: 2px; }
.d-meta { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 5px; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.tier-mark {
  font-size: 12px; font-weight: 600;
  padding-left: 8px; border-left: 2px solid #cbd5e1;
}
.tier-mark.pass { border-left-color: #0d7a5f; color: #0d7a5f; }
.tier-mark.fail { border-left-color: #ef4444; color: #ef4444; }

.d-section { margin-top: 14px; }
.d-label { font-size: 12px; color: var(--el-text-color-secondary); margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
.d-reason { font-size: 14px; line-height: 1.7; color: var(--el-text-color-primary); }
.d-actions { display: flex; align-items: center; margin-top: 10px; }
.grow { flex: 1; }

.empty-state { display: flex; flex-direction: column; align-items: center; gap: 8px; padding: 60px 20px; justify-content: center; align-self: stretch; }
.empty-title { font-size: 15px; font-weight: 700; }
.empty-hint { font-size: 12.5px; color: var(--el-text-color-secondary); }
</style>
