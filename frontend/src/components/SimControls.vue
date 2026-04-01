<template>
  <div class="ws-sim-controls">
    <h4>推演控制</h4>

    <button class="ws-btn primary" v-if="canStart" @click="$emit('start')">
      开始推演
    </button>
    <button class="ws-btn primary" v-if="status === 'paused'" @click="$emit('resume')">
      继续推演
    </button>

    <button class="ws-btn" v-if="status === 'running'" @click="$emit('pause')">
      暂停
    </button>
    <button class="ws-btn danger" v-if="status === 'running' || status === 'paused'" @click="$emit('stop')">
      停止
    </button>

    <div class="ws-inject" v-if="status === 'running' || status === 'paused'">
      <label>注入事件</label>
      <div class="ws-inject-row">
        <input v-model="eventText" placeholder="突发事件描述..." @keyup.enter="doInject" />
        <button class="ws-btn" @click="doInject" :disabled="!eventText.trim()">注入</button>
      </div>
    </div>

    <div v-if="status === 'done'" class="ws-sim-done-controls">
      <router-link :to="`/report/${scenarioId}`" class="ws-btn primary" style="display:block;text-align:center">
        查看报告
      </router-link>
      <button class="ws-btn" @click="$emit('reset')" style="width:100%;text-align:center;margin-top:8px">
        重新推演
      </button>
    </div>
  </div>
</template>

<script>
import { ref, computed } from 'vue'

export default {
  name: 'SimControls',
  props: {
    status: { type: String, default: 'idle' },
    scenarioId: { type: Number, required: true },
  },
  emits: ['start', 'pause', 'resume', 'stop', 'inject', 'reset'],
  setup(props, { emit }) {
    const eventText = ref('')
    const canStart = computed(() =>
      ['idle', 'draft', 'ready', 'stopped'].includes(props.status)
    )

    function doInject() {
      if (eventText.value.trim()) {
        emit('inject', eventText.value.trim())
        eventText.value = ''
      }
    }

    return { eventText, canStart, doInject }
  },
}
</script>
