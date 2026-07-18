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

const sortedJobs = computed(() => {
  const list = [...props.jobs]
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

    <!-- 卡片列表 -->
    <TransitionGroup name="card-in" tag="div" class="cards">
      <JobCard v-for="(job, idx) in sortedJobs" :key="job.securityId || job.encryptJobId || idx"
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
