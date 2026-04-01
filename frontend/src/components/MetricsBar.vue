<template>
  <div class="ws-metrics-bar">
    <div class="ws-metric" v-for="m in metricDefs" :key="m.key" :class="m.key">
      <div class="ws-metric-label">{{ m.label }}</div>
      <div class="ws-metric-bar">
        <div class="ws-metric-fill" :style="{ width: clamped(metrics[m.key]) + '%' }"></div>
      </div>
      <div class="ws-metric-value">{{ Math.round(clamped(metrics[m.key])) }}</div>
    </div>
  </div>
</template>

<script>
export default {
  name: 'MetricsBar',
  props: {
    metrics: { type: Object, default: () => ({ darkness: 0, pressure: 0, stability: 50, hope: 50 }) },
  },
  setup() {
    const metricDefs = [
      { key: 'darkness', label: '黑暗' },
      { key: 'pressure', label: '压力' },
      { key: 'stability', label: '稳定' },
      { key: 'hope', label: '希望' },
    ]
    const clamped = (v) => Math.max(0, Math.min(100, Number(v) || 0))
    return { metricDefs, clamped }
  },
}
</script>
