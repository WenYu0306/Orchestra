<template>
  <div class="record-table">
    <n-empty v-if="records.length === 0" description="暂无投递记录" />

    <n-data-table
      v-else
      :columns="columns"
      :data="records"
      :bordered="false"
      :single-line="false"
      :row-key="rowKey"
      size="small"
      virtual-scroll
      :max-height="500"
    />
  </div>
</template>

<script setup>
import { h, computed } from 'vue'
import { NDataTable, NTag, NTooltip, NEmpty } from 'naive-ui'

const props = defineProps({
  records: { type: Array, default: () => [] },
})

const rowKey = (row, index) => `${row.company}-${row.position}-${index}`

const columns = computed(() => [
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
    sorter: (a, b) => a.score - b.score,
    defaultSortOrder: 'descend',
    render(row) {
      const type = row.score >= 80 ? 'success' : row.score >= 60 ? 'info' : 'warning'
      return h(NTag, { type, size: 'small', bordered: false }, { default: () => String(row.score) })
    },
  },
  {
    title: '匹配理由',
    key: 'reason',
    width: 280,
    ellipsis: { tooltip: true },
    render(row) {
      return h(
        NTooltip,
        { trigger: 'hover', style: { maxWidth: '360px' } },
        {
          trigger: () => h('span', { class: 'reason-text' }, row.reason),
          default: () => row.reason,
        }
      )
    },
  },
  {
    title: '投递状态',
    key: 'status',
    width: 100,
    render(row) {
      const statusMap = {
        success: { type: 'success', text: '✓ 成功' },
        partial: { type: 'warning', text: '⚠ 部分填写' },
        failed: { type: 'error', text: '✗ 失败' },
      }
      const s = statusMap[row.status] || { type: 'default', text: row.status }
      return h(NTag, { type: s.type, size: 'small', bordered: false }, { default: () => s.text })
    },
  },
  {
    title: '层级',
    key: 'tier',
    width: 80,
    render(row) {
      const tierMap = {
        high: { type: 'success', text: '高匹配' },
        medium: { type: 'info', text: '中匹配' },
        try: { type: 'warning', text: '可尝试' },
      }
      const t = tierMap[row.tier] || { type: 'default', text: row.tier }
      return h(NTag, { type: t.type, size: 'small', bordered: false }, { default: () => t.text })
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
])
</script>

<style scoped>
.record-table {
  min-height: 300px;
}

.reason-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
  max-width: 260px;
  cursor: default;
}

.time-cell {
  font-family: 'SF Mono', 'Fira Code', monospace;
  color: #888;
  font-size: 13px;
}
</style>
