<template>
  <div class="ws-timeline">
    <h4>时间线</h4>
    <div class="ws-timeline-list" ref="timelineList">
      <div class="ws-timeline-item" v-for="(e, i) in events" :key="i"
        :class="e.type || 'narrative'">
        <div class="ws-timeline-year">
          <span>{{ e.year }}年</span>
          <span class="ws-timeline-type" v-if="e.type && e.type !== 'narrative'">{{ typeLabel(e.type) }}</span>
        </div>
        <div class="ws-timeline-content">
          <span v-if="!expandedSet.has(i) && (e.content || '').length > 120">
            {{ (e.content || '').slice(0, 120) }}...
            <button class="ws-timeline-expand" @click="expandedSet.add(i); expandedSet = new Set(expandedSet)">展开</button>
          </span>
          <span v-else>{{ e.content }}</span>
        </div>
      </div>
      <div class="ws-timeline-empty" v-if="!events.length">
        暂无事件
      </div>
    </div>
  </div>
</template>

<script>
import { ref, watch, nextTick } from 'vue'

export default {
  name: 'Timeline',
  props: { events: { type: Array, default: () => [] } },
  setup(props) {
    const timelineList = ref(null)
    let expandedSet = ref(new Set())

    watch(() => props.events.length, async () => {
      await nextTick()
      if (timelineList.value) {
        timelineList.value.scrollTop = timelineList.value.scrollHeight
      }
    })

    function typeLabel(type) {
      const map = { injected: '外部事件', ending: '结局', decision: '决策', milestone: '里程碑' }
      return map[type] || type
    }

    return { timelineList, expandedSet, typeLabel }
  },
}
</script>
