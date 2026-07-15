<script setup>
import { computed } from 'vue'

const props = defineProps({ status: String, matched: Number })
const emit = defineEmits(['start', 'stop', 'uploadResume'])

const pill = computed(() => {
  switch (props.status) {
    case 'running': return { cls: 'running', text: `运行中 · 已匹配 ${props.matched} 个` }
    case 'captcha': return { cls: 'captcha', text: '遇到验证码 · 等待处理' }
    case 'done': return { cls: 'done', text: `已完成 · 共匹配 ${props.matched} 个` }
    case 'error': return { cls: 'error', text: '出错 · 请查看日志' }
    default: return { cls: 'idle', text: '就绪 · 等待启动' }
  }
})

const isRunning = computed(() => props.status === 'running')
</script>

<template>
  <header class="top-bar glass">
    <!-- Logo -->
    <div class="logo-wrap">
      <div class="logo-mark">
        <span class="bar" style="height:10px;top:11px;left:8px"></span>
        <span class="bar" style="height:18px;top:7px;left:12.5px"></span>
        <span class="bar" style="height:6px;top:13px;left:17px"></span>
        <span class="bar" style="height:14px;top:9px;left:21.5px"></span>
      </div>
      <span class="logo-text">Orchestra</span>
    </div>

    <!-- 标题 -->
    <div class="title-wrap">
      <div class="title-main">Orchestra</div>
      <div class="title-sub">AI Agent 控制台</div>
    </div>

    <!-- 控制区 -->
    <div class="ctrl-wrap">
      <label class="upload-btn" title="上传简历">
        <input type="file" accept=".pdf" @change="$emit('uploadResume', $event)" style="display:none" />
        <svg viewBox="0 0 14 14" width="14" height="14"><path d="M3 9 L7 5 L11 9 M7 5 L7 13 M2 3 H12" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
        <span>简历</span>
      </label>
      <div class="status-pill" :class="pill.cls">
        <span class="dot"></span>
        <span class="status-text">{{ pill.text }}</span>
      </div>

      <button class="btn btn-stop" :disabled="!isRunning" @click="emit('stop')">
        <span class="ico-stop"></span>
        <span>停止</span>
      </button>

      <button class="btn btn-start" :disabled="isRunning" @click="emit('start')">
        <svg class="ico-start" viewBox="0 0 14 14" width="14" height="14">
          <path d="M4 2.5 L11 7 L4 11.5 Z" fill="currentColor" />
        </svg>
        <span>开始</span>
      </button>
    </div>
  </header>
</template>

<style scoped>
.top-bar {
  height: 76px;
  display: flex;
  align-items: center;
  gap: 20px;
  padding: 0 32px;
  margin: 16px 0 12px;
  border-radius: 20px;
  box-shadow:
    inset 0 1px 2px rgba(255,255,255,0.25),
    inset 0 2px 8px rgba(99,102,241,0.15),
    0 8px 32px rgba(0,0,0,0.06);
}

/* Logo */
.logo-wrap {
  display: flex; align-items: center; gap: 12px;
  filter: drop-shadow(0 0 20px rgba(99, 102, 241, 0.08));
}
.logo-mark {
  position: relative;
  width: 32px; height: 32px;
  border-radius: 8px;
  background: linear-gradient(135deg, #A78BFA 0%, #7DD3FC 100%);
}
.logo-mark .bar {
  position: absolute;
  width: 2.5px;
  background: #fff;
  border-radius: 1px;
}
.logo-text {
  font-family: var(--font-en);
  font-weight: 600;
  font-size: 18px;
  color: var(--text-1);
}

/* 标题 */
.title-wrap {
  flex: 1;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 2px;
}
.title-main { font-family: var(--font-en); font-weight: 600; font-size: 15px; color: var(--text-1); }
.title-sub { font-size: 12px; color: var(--text-2); }

/* 控制区 */
.ctrl-wrap { display: flex; align-items: center; gap: 12px; }

.status-pill {
  display: flex; align-items: center; gap: 8px;
  height: 31px; padding: 0 14px;
  border-radius: 999px;
  border: 1px solid transparent;
}
.status-pill .dot {
  width: 8px; height: 8px; border-radius: 999px;
  background: var(--text-3);
}
.status-pill .status-text { font-size: 12px; font-weight: 500; }

.status-pill.running {
  background: var(--green-soft); border-color: var(--green-border);
}
.status-pill.running .dot {
  background: var(--green);
  animation: pulse 1.8s ease-in-out infinite;
}
.status-pill.running .status-text { color: var(--green-dark); }

.status-pill.idle { background: rgba(148,163,184,0.08); border-color: rgba(148,163,184,0.25); }
.status-pill.idle .status-text { color: var(--text-2); }

.status-pill.captcha { background: var(--amber-soft); border-color: var(--amber-border); }
.status-pill.captcha .dot { background: var(--amber); }
.status-pill.captcha .status-text { color: #B45309; }

.status-pill.done { background: var(--green-soft); border-color: var(--green-border); }
.status-pill.done .dot { background: var(--green); }
.status-pill.done .status-text { color: var(--green-dark); }

.status-pill.error { background: rgba(239,68,68,0.08); border-color: rgba(239,68,68,0.25); }
.status-pill.error .dot { background: var(--red); }
.status-pill.error .status-text { color: var(--red); }

@keyframes pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(16,185,129,0.5), 0 0 6px 2px rgba(16,185,129,0.8); }
  50% { box-shadow: 0 0 0 6px rgba(16,185,129,0), 0 0 12px 4px rgba(16,185,129,0.5); }
}

/* 按钮 */
.btn {
  display: flex; align-items: center; gap: 6px;
  height: 35px; padding: 0 14px;
  border-radius: 12px;
  font-size: 13px; font-weight: 600;
  transition: transform .2s, box-shadow .2s, opacity .2s;
}
.btn:disabled { opacity: 0.45; cursor: not-allowed; }
.btn:not(:disabled):hover { transform: translateY(-1px); }

.btn-stop {
  background: var(--red); color: #fff;
  box-shadow: 0 4px 12px rgba(239,68,68,0.25), inset 0 1px 0 rgba(255,255,255,0.2);
}
.ico-stop {
  width: 10px; height: 10px; background: #fff; border-radius: 2px;
}

.btn-start {
  background: #F0F1F5; color: var(--text-3);
  border: 1px solid #E0E1E8;
}
.btn-start:not(:disabled) { color: var(--text-2); }
.upload-btn {
  display: flex; align-items: center; gap: 4px;
  height: 35px; padding: 0 12px;
  border-radius: 12px; border: 1px solid #E0E1E8;
  background: #F8FAFC; color: var(--text-2);
  font-size: 12px; cursor: pointer;
  transition: border-color .2s, color .2s;
}
.upload-btn:hover { border-color: var(--indigo-border); color: var(--indigo); }
</style>
