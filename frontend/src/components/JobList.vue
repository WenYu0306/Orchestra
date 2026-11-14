<script setup>
import { ref, computed } from 'vue'
import JobCard from './JobCard.vue'

const props = defineProps({ jobs: Array, loading: Boolean, selectedCount: Number })
const emit = defineEmits(['send'])

const sort = ref('score')
const sorts = [
  { key: 'score', label: '按分数' },
  { key: 'salary', label: '按薪资' },
  { key: 'time', label: '按时间' },
]

// 分层 Tab：可投递（≥投递线，默认） / 低于投递线（review_only，默认折叠不渲染——
// 110 卡全量渲染 + 毛玻璃在老机器上会卡，折叠同时是性能修复）
const activeTab = ref('sendable')
const sendableJobs = computed(() => props.jobs.filter(j => j.status !== 'review_only'))
const belowJobs = computed(() => props.jobs.filter(j => j.status === 'review_only'))
const tabJobs = computed(() => activeTab.value === 'sendable' ? sendableJobs.value : belowJobs.value)

const sortedJobs = computed(() => {
  const list = [...tabJobs.value]
  if (sort.value === 'score') {
    list.sort((a, b) => (b.score || 0) - (a.score || 0))
  } else if (sort.value === 'salary') {
    const salNum = (s) => {
      if (!s) return 0
      const m = String(s).match(/(\d+)/)
      return m ? parseInt(m[1]) : 0
    }
    list.sort((a, b) => salNum(b.salary) - salNum(a.salary))
  } else if (sort.value === 'time') {
    list.reverse()
  }
  return list
})
</script>

<template>
  <section class="job-list">
    <!-- 标题行 -->
    <div class="head">
      <div class="title-group">
        <h2 class="title">匹配职位</h2>
        <span class="count-pill">{{ sortedJobs.length }} 条</span>
      </div>
      <div class="sort-group">
        <button
          class="sort-btn send-btn"
          :disabled="selectedCount === 0"
          @click="emit('send')"
        >发送选中 {{ selectedCount }}</button>
        <button
          v-for="s in sorts" :key="s.key"
          class="sort-btn" :class="{ active: sort === s.key }"
          @click="sort = s.key"
        >{{ s.label }}</button>
      </div>
    </div>

    <!-- 分层 Tab -->
    <div v-if="props.jobs.length" class="tabs">
      <button class="tab" :class="{ active: activeTab === 'sendable' }"
              @click="activeTab = 'sendable'">可投递 · {{ sendableJobs.length }}</button>
      <button class="tab below" :class="{ active: activeTab === 'below' }"
              @click="activeTab = 'below'">低于投递线 · {{ belowJobs.length }}</button>
    </div>

    <!-- 空状态引导（替代纯"等待启动"） -->
    <div v-if="!loading && !props.jobs.length" class="empty-state">
      <div class="empty-emoji">🎯</div>
      <div class="empty-title">还没有匹配的岗位</div>
      <div class="empty-hint">点右上角「开始」，AI 会按你的简历自动搜索、逐个打分、写好招呼语</div>
    </div>
    <div v-else-if="!loading && !sortedJobs.length" class="empty-state slim">
      <div class="empty-hint">这个分类暂无岗位</div>
    </div>

    <!-- 卡片列表 -->
    <TransitionGroup name="card-in" tag="div" class="cards">
      <JobCard v-for="job in sortedJobs" :key="job.uid || (job.company + job.title)"
        :job="job" />
    </TransitionGroup>

    <!-- 骨架卡（分析中） -->
    <div v-if="loading" class="skeleton-card">
      <div class="skel-top">
        <div class="skel-left">
          <div class="skel-company">
            <span class="skel-block" style="width:34px;height:34px;border-radius:10px"></span>
            <span class="skel-block" style="width:70px;height:16px"></span>
          </div>
          <span class="skel-block" style="width:170px;height:12px"></span>
        </div>
        <span class="analyzing">分析中</span>
      </div>
      <span class="skel-block skel-line" style="width:60%;height:11px"></span>
      <div class="skel-greeting">
        <span class="skel-block" style="width:64px;height:10px"></span>
        <span class="skel-block" style="width:90%;height:11px"></span>
      </div>
    </div>
  </section>
</template>

<style scoped>
.job-list { padding: 0 32px 24px; display: flex; flex-direction: column; gap: 14px; }

.head { display: flex; align-items: center; justify-content: space-between; height: 29px; }
.title-group { display: flex; align-items: center; gap: 10px; }
.title { font-family: var(--font-en); font-weight: 600; font-size: 16px; color: var(--text-1); }
.count-pill {
  padding: 3px 8px;
  background: #F0F1F5;
  border-radius: 999px;
  font-family: var(--font-mono); font-weight: 500; font-size: 11px;
  color: var(--text-2);
}

.sort-group { display: flex; gap: 8px; }
.sort-btn {
  height: 29px; padding: 0 12px;
  background: #F0F1F5;
  border-radius: 8px;
  font-size: 12px; font-weight: 500; color: var(--text-2);
  transition: background .2s, color .2s;
}
.sort-btn.active {
  background: var(--green-soft);
  color: var(--green-dark);
  box-shadow: inset 0 0 0 1px var(--green-border);
}
.send-btn {
  background: var(--indigo);
  color: #fff;
  font-weight: 600;
  transition: opacity .2s;
}
.send-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}
.send-btn:not(:disabled):hover {
  opacity: 0.88;
}

.cards { display: flex; flex-direction: column; gap: 14px; }

/* 分层 Tab */
.tabs { display: flex; gap: 8px; }
.tab {
  height: 30px; padding: 0 14px;
  background: #F0F1F5; border-radius: 999px;
  font-size: 12px; font-weight: 500; color: var(--text-2);
  transition: all .2s;
}
.tab.active {
  background: var(--indigo-soft, rgba(99,102,241,0.1));
  color: var(--indigo, #6366f1);
  font-weight: 600;
  box-shadow: inset 0 0 0 1px var(--indigo-border, rgba(99,102,241,0.35));
}
.tab.below.active {
  background: rgba(245, 158, 11, 0.1);
  color: #b45309;
  box-shadow: inset 0 0 0 1px rgba(245, 158, 11, 0.35);
}

/* 空状态 */
.empty-state {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  gap: 8px; padding: 48px 20px;
  background: rgba(255, 255, 255, 0.4);
  border: 1px dashed rgba(148, 163, 184, 0.35);
  border-radius: 20px;
}
.empty-state.slim { padding: 20px; }
.empty-emoji { font-size: 32px; }
.empty-title { font-size: 15px; font-weight: 600; color: var(--text-1); }
.empty-hint { font-size: 12.5px; color: var(--text-2); }

/* 入场：淡入上浮 */
.card-in-enter-active { transition: all .5s cubic-bezier(.2, .8, .2, 1); }
.card-in-enter-from { opacity: 0; transform: translateY(16px); }

/* 骨架卡 */
.skeleton-card {
  display: flex; flex-direction: column; gap: 14px;
  padding: 20px;
  background: rgba(255, 255, 255, 0.4);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.4);
  border-radius: 20px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.03);
}
.skel-top { display: flex; justify-content: space-between; }
.skel-left { display: flex; flex-direction: column; gap: 9px; }
.skel-company { display: flex; align-items: center; gap: 9px; }
.skel-block { display: block; background: #E2E8F0; border-radius: 4px; }
.analyzing { font-size: 10.5px; font-weight: 500; color: var(--text-3); }
.skel-line { margin-top: 4px; }
.skel-greeting {
  display: flex; flex-direction: column; gap: 7px;
  padding: 14px;
  background: #F7F8FA;
  border: 1px solid rgba(224, 227, 234, 0.4);
  border-radius: 12px;
}

/* 骨架占位条呼吸 */
@keyframes shimmer {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}
.skel-block { animation: shimmer 1.6s ease-in-out infinite; }
</style>
