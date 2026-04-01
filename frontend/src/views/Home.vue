<template>
  <div class="ws-page">
    <div class="ws-hero">
      <h2>WorldSim</h2>
      <p>多智能体世界推演引擎 - 模拟未来，预见变局</p>
      <button class="ws-btn primary" @click="newScenario">+ 新建推演</button>
    </div>

    <div class="ws-section" v-if="scenarios.length">
      <h3>历史推演</h3>
      <div class="ws-card-list">
        <div class="ws-card" v-for="s in scenarios" :key="s.id" @click="openScenario(s.id)">
          <div class="ws-card-title">{{ s.name }}</div>
          <div class="ws-card-meta">
            <span class="ws-tag" :class="s.status">{{ statusLabel(s.status) }}</span>
            <span>{{ s.entity_count }} 实体 / {{ s.max_rounds }} 轮</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listScenarios, createScenario } from '../api.js'

export default {
  name: 'Home',
  setup() {
    const router = useRouter()
    const scenarios = ref([])

    onMounted(async () => {
      try {
        scenarios.value = await listScenarios()
      } catch (e) {
        console.error('Failed to load scenarios', e)
      }
    })

    async function newScenario() {
      const data = await createScenario({ name: '新推演项目' })
      router.push({ name: 'setup', params: { id: data.id } })
    }

    function openScenario(id) {
      router.push({ name: 'setup', params: { id } })
    }

    function statusLabel(status) {
      const map = {
        draft: '草稿', ready: '就绪', running: '运行中',
        paused: '已暂停', done: '已完成',
      }
      return map[status] || status
    }

    return { scenarios, newScenario, openScenario, statusLabel }
  },
}
</script>
