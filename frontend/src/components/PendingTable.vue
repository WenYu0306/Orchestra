<template>
  <div class="pending-table">
    <div class="pending-header">
      <span class="pending-title">待选区</span>
      <n-tag type="info" size="small" :bordered="false">
        {{ items.length }} / 5
      </n-tag>
    </div>

    <n-empty v-if="items.length === 0" description="暂无待选职位" />

    <n-data-table
      v-else
      :columns="columns"
      :data="items"
      :bordered="false"
      :single-line="false"
      :row-key="rowKey"
      size="small"
    />
  </div>
</template>

<script setup>
import { h, computed } from 'vue'
import { NDataTable, NTag, NTooltip, NEmpty } from 'naive-ui'

defineProps({
  items: { type: Array, default: () => [] },
})

const rowKey = (row, index) => `pending-${row.company}-${index}`

const columns = [
  {
    title: '公司',
    key: 'company',
    width: 140,
    ellipsis: { tooltip: true },
  },
  {
    title: '职位',
    key: 'position',
    width: 200,
    ellipsis: { tooltip: true },
    render(row) {
      return h('span', { style: { fontWeight: 600 } }, row.position)
    },
  },
  {
    title: '匹配分数',
    key: 'score',
    width: 100,
    render(row) {
      const type = row.score >= 80 ? 'success' : row.score >= 60 ? 'info' : 'warning'
      return h(NTag, { type, size: 'small', bordered: false }, { default: () => String(row.score) })
    },
  },
  {
    title: '降级原因',
    key: 'downgrade_reason',
    width: 300,
    ellipsis: { tooltip: true },
    render(row) {
      return h(
        NTooltip,
        { trigger: 'hover' },
        {
          trigger: () => h('span', { class: 'reason-text' }, row.downgrade_reason),
          default: () => row.downgrade_reason,
        }
      )
    },
  },
  {
    title: '时间',
    key: 'timestamp',
    width: 120,
    render(row) {
      return h('span', { class: 'time-cell' }, row.timestamp)
    },
  },
]
</script>

<style scoped>
.pending-table {
  min-height: 200px;
}

.pending-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.pending-title {
  font-weight: 600;
  font-size: 15px;
  color: #a855f7;
}

.reason-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
  max-width: 280px;
  cursor: default;
}

.time-cell {
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: #888;
  font-size: 13px;
}
</style>
