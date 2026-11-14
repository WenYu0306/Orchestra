<script setup>
defineProps({ matched: Number, delivered: Number })
</script>

<template>
  <footer class="bottom-bar">
    <span class="left">匹配 {{ matched }} 个 · 已发送 {{ delivered }} 个</span>
    <span class="right">DeepSeek-V3 · Orchestra Agent</span>
  </footer>
</template>

<style scoped>
.bottom-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 4px 4px;
}
.left, .right { font-size: 12px; color: var(--el-text-color-secondary); }
</style>
