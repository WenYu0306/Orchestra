<script setup>
import JobCard from './JobCard.vue'
defineProps({ jobs: Array, loading: Boolean })
</script>

<template>
  <section class="job-list">
    <div class="head">
      <div class="title-group">
        <h2 class="title">匹配职位</h2>
        <span class="count-pill">{{ jobs.length }} 条</span>
      </div>
    </div>
    <TransitionGroup name="card-in" tag="div" class="cards">
      <JobCard v-for="(job, i) in jobs" :key="i" :job="job" />
    </TransitionGroup>
    <div v-if="loading && jobs.length === 0" class="skeleton-card">
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
.job-list { padding:0 32px 24px; display:flex; flex-direction:column; gap:14px; }
.head { display:flex; align-items:center; justify-content:space-between; height:29px; }
.title-group { display:flex; align-items:center; gap:10px; }
.title { font-family:var(--font-en); font-weight:600; font-size:16px; color:var(--text-1); }
.count-pill { padding:3px 8px; background:#F0F1F5; border-radius:999px; font-family:var(--font-mono); font-weight:500; font-size:11px; color:var(--text-2); }
.cards { display:flex; flex-direction:column; gap:14px; }
.card-in-enter-active { transition:all .5s cubic-bezier(.2,.8,.2,1); }
.card-in-enter-from { opacity:0; transform:translateY(16px); }
.skeleton-card { display:flex; flex-direction:column; gap:14px; padding:20px; background:rgba(255,255,255,0.4); backdrop-filter:blur(16px); -webkit-backdrop-filter:blur(16px); border:1px solid rgba(255,255,255,0.4); border-radius:20px; box-shadow:0 4px 12px rgba(0,0,0,0.03); }
.skel-top { display:flex; justify-content:space-between; }
.skel-left { display:flex; flex-direction:column; gap:9px; }
.skel-company { display:flex; align-items:center; gap:9px; }
.skel-block { display:block; background:#E2E8F0; border-radius:4px; }
.analyzing { font-size:10.5px; font-weight:500; color:var(--text-3); }
.skel-line { margin-top:4px; }
.skel-greeting { display:flex; flex-direction:column; gap:7px; padding:14px; background:#F7F8FA; border:1px solid rgba(224,227,234,0.4); border-radius:12px; }
@keyframes shimmer { 0%{opacity:0.6} 50%{opacity:1} 100%{opacity:0.6} }
.skel-block { animation:shimmer 1.6s ease-in-out infinite; }
</style>
