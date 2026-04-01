<template>
  <div class="ws-page">
    <div class="ws-section" v-if="!generated">
      <h3>生成实体</h3>
      <p>根据场景设定，LLM 将批量生成推演实体（含角色卡）</p>
      <button class="ws-btn primary" @click="doGenerate" :disabled="generating">
        {{ generating ? `生成中... ${genProgress}` : '开始生成' }}
      </button>
    </div>

    <div class="ws-section" v-if="generated">
      <div class="ws-section-header">
        <h3>实体概览 ({{ total }} 个实体)</h3>
        <div>
          <button class="ws-btn" @click="showAddEntity = true">+ 手动添加</button>
          <button class="ws-btn primary" @click="startSimulation">开始推演</button>
        </div>
      </div>

      <!-- Faction list -->
      <FactionList :factions="factions" @edit="editEntity" @delete="confirmDelete" />
    </div>

    <!-- Entity Editor Drawer -->
    <EntityEditor v-if="editingEntity" :entity="editingEntity"
      @save="saveEntity" @close="editingEntity = null" />
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { listEntities, generateEntities, updateEntity, deleteEntity } from '../api.js'
import FactionList from '../components/FactionList.vue'
import EntityEditor from '../components/EntityEditor.vue'
import { useToast } from '../components/Toast.js'

export default {
  name: 'EntitiesView',
  components: { FactionList, EntityEditor },
  props: { id: String },
  setup(props) {
    const { show: showToast } = useToast()
    const router = useRouter()
    const scenarioId = parseInt(props.id)
    const generated = ref(false)
    const generating = ref(false)
    const genProgress = ref('')
    const factions = ref({})
    const total = ref(0)
    const editingEntity = ref(null)
    const showAddEntity = ref(false)

    onMounted(async () => {
      await loadEntities()
    })

    async function loadEntities() {
      try {
        const data = await listEntities(scenarioId)
        factions.value = data.factions || {}
        total.value = data.total || 0
        generated.value = total.value > 0
      } catch (e) {
        console.error('Failed to load entities', e)
      }
    }

    async function doGenerate() {
      generating.value = true
      genProgress.value = '生成阵营...'
      try {
        const result = await generateEntities(scenarioId)
        total.value = result.total
        await loadEntities()
      } catch (e) {
        showToast('生成失败: ' + (e.response?.data?.error || e.message))
      } finally {
        generating.value = false
      }
    }

    function editEntity(entity) {
      editingEntity.value = { ...entity }
    }

    async function saveEntity(entity) {
      await updateEntity(entity.id, entity)
      editingEntity.value = null
      await loadEntities()
    }

    async function confirmDelete(entity) {
      if (!confirm(`确认删除 ${entity.name}?`)) return
      await deleteEntity(entity.id)
      await loadEntities()
    }

    function startSimulation() {
      router.push({ name: 'simulation', params: { id: scenarioId } })
    }

    return {
      generated, generating, genProgress, factions, total,
      editingEntity, showAddEntity,
      doGenerate, editEntity, saveEntity, confirmDelete, startSimulation,
    }
  },
}
</script>
