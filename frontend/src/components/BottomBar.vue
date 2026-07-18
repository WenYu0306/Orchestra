<script setup>
defineProps({ matched: Number, delivered: Number })
</script>

<template>
  <footer class="bottom-bar glass">
    <span class="left">匹配 {{ matched }} 个 · 已发送 {{ delivered }} 个</span>
    <span class="right">DeepSeek-V3 · Orchestra Agent</span>
  </footer>
</template>

<style scoped>
.bottom-bar {
  display: flex; align-items: center; justify-content: space-between;
  height: 36px;
  padding: 0 32px;
  border-radius: 0;
  border-left: none; border-right: none; border-bottom: none;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.2), 0 -4px 16px rgba(0,0,0,0.04);
}
.left, .right { font-size: 11px; color: var(--text-3); }
.right { color: var(--text-4); }
</style>
