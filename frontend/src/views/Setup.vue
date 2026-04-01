<template>
  <div class="ws-page">
    <div class="ws-section">
      <h3>场景设定</h3>

      <div class="ws-form-group">
        <label>场景名称</label>
        <input v-model="form.name" type="text" placeholder="为这次推演命名..." />
      </div>

      <div class="ws-form-group">
        <label>世界背景 / 种子材料</label>
        <textarea v-model="form.background" rows="5"
          placeholder="描述你要推演的世界背景...&#10;例如：AI在3-5年内替代掉85%的白领工作..."></textarea>
      </div>

      <div class="ws-form-group">
        <label>推演问题</label>
        <input v-model="form.question" type="text" placeholder="你想推演什么？" />
      </div>

      <div class="ws-form-group">
        <label>世界规则（可选，每行一条）</label>
        <textarea v-model="form.rules" rows="3"
          placeholder="1. 技术采用呈指数曲线&#10;2. 政策滞后于技术1-2年"></textarea>
      </div>

      <!-- File Upload -->
      <div class="ws-form-group">
        <label>参考素材文件（PDF/TXT/MD）</label>
        <FileUpload :scenario-id="scenarioId" @uploaded="onFilesUploaded" />
      </div>

      <div class="ws-form-group" v-if="hasFiles">
        <button class="ws-btn" @click="parseRulesFromFiles" :disabled="parsingRules">
          {{ parsingRules ? '提炼中...' : '从素材提炼世界规则' }}
        </button>
      </div>

      <div class="ws-config-row">
        <label>实体数 <input v-model.number="form.entity_count" type="number" min="10" max="300" style="width:60px" /></label>
        <label>轮次 <input v-model.number="form.max_rounds" type="number" min="2" max="20" style="width:55px" /></label>
        <label>起始年 <input v-model.number="form.start_year" type="number" style="width:65px" /></label>
      </div>

      <!-- Advanced Config (collapsible) -->
      <details class="ws-advanced-config" open>
        <summary>时间与推演设置</summary>
        <div class="ws-config-grid">
          <div class="ws-form-group">
            <label>时间单位</label>
            <select v-model="form.time_unit">
              <option value="month">月</option>
              <option value="quarter">季度</option>
            </select>
          </div>
          <div class="ws-form-group">
            <label>总时长 (ticks)</label>
            <input v-model.number="form.total_duration" type="number" min="6" max="240" />
            <small class="ws-hint">{{ form.time_unit === 'month' ? `${(form.total_duration/12).toFixed(1)}年` : `${(form.total_duration/4).toFixed(1)}年` }}</small>
          </div>
          <div class="ws-form-group">
            <label>总结间隔 (ticks)</label>
            <input v-model.number="form.summary_interval" type="number" min="2" max="24" />
            <small class="ws-hint">每{{ form.summary_interval }}个tick生成一次阶段总结</small>
          </div>
        </div>
      </details>

      <details class="ws-advanced-config">
        <summary>初始指标</summary>
        <div class="ws-config-grid">
          <div class="ws-form-group">
            <label>黑暗度 <span class="ws-metric-val" :style="{color: metricColor(form.darkness_base)}">{{ form.darkness_base }}</span></label>
            <input v-model.number="form.darkness_base" type="range" min="0" max="100" step="1" />
          </div>
          <div class="ws-form-group">
            <label>压力值 <span class="ws-metric-val" :style="{color: metricColor(form.pressure_base)}">{{ form.pressure_base }}</span></label>
            <input v-model.number="form.pressure_base" type="range" min="0" max="100" step="1" />
          </div>
          <div class="ws-form-group">
            <label>稳定度 <span class="ws-metric-val" :style="{color: metricColor(form.stability_base, true)}">{{ form.stability_base }}</span></label>
            <input v-model.number="form.stability_base" type="range" min="0" max="100" step="1" />
          </div>
          <div class="ws-form-group">
            <label>希望值 <span class="ws-metric-val" :style="{color: metricColor(form.hope_base, true)}">{{ form.hope_base }}</span></label>
            <input v-model.number="form.hope_base" type="range" min="0" max="100" step="1" />
          </div>
        </div>
      </details>

      <details class="ws-advanced-config">
        <summary>结局条件</summary>
        <div class="ws-config-grid">
          <div class="ws-form-group">
            <label>Bad End 黑暗阈值</label>
            <input v-model.number="ending.bad_darkness" type="range" min="50" max="100" />
            <small class="ws-hint">黑暗度 ≥ {{ ending.bad_darkness }} 触发 Bad End</small>
          </div>
          <div class="ws-form-group">
            <label>Bad End 压力阈值</label>
            <input v-model.number="ending.bad_pressure" type="range" min="50" max="100" />
            <small class="ws-hint">压力值 ≥ {{ ending.bad_pressure }} 触发 Bad End</small>
          </div>
          <div class="ws-form-group">
            <label>Good End 希望阈值</label>
            <input v-model.number="ending.good_hope" type="range" min="30" max="100" />
          </div>
          <div class="ws-form-group">
            <label>Good End 稳定阈值</label>
            <input v-model.number="ending.good_stability" type="range" min="20" max="100" />
            <small class="ws-hint">希望 ≥ {{ ending.good_hope }} 且 稳定 ≥ {{ ending.good_stability }} = Good End</small>
          </div>
          <div class="ws-form-group">
            <label>指标变化幅度上限</label>
            <input v-model.number="ending.max_delta" type="number" min="3" max="30" style="width:70px" />
            <small class="ws-hint">每tick指标最大变化量</small>
          </div>
        </div>
      </details>

      <details class="ws-advanced-config">
        <summary>大事件触发规则</summary>
        <small class="ws-hint" style="margin-bottom:8px;display:block">每条规则是一个自然语言条件，满足时触发大事件。LLM也会每3个tick自主判断。</small>
        <div v-for="(rule, i) in triggers" :key="i" class="ws-trigger-row">
          <input v-model="triggers[i].condition" type="text" placeholder="例: 失业率超过15%时" />
          <button class="ws-btn-sm danger" @click="triggers.splice(i, 1)">删除</button>
        </div>
        <button class="ws-btn-sm" @click="triggers.push({condition: ''})">+ 添加规则</button>
      </details>

      <div class="ws-btn-row">
        <button class="ws-btn primary" @click="save" :disabled="saving">
          {{ saving ? '保存中...' : '保存' }}
        </button>
        <button class="ws-btn primary" @click="saveAndGenerate" :disabled="saving">
          保存并生成实体
        </button>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { getScenario, updateScenario, parseRules } from '../api.js'
import FileUpload from '../components/FileUpload.vue'

export default {
  name: 'Setup',
  components: { FileUpload },
  props: { id: String },
  setup(props) {
    const router = useRouter()
    const scenarioId = ref(parseInt(props.id) || 0)
    const saving = ref(false)
    const parsingRules = ref(false)
    const hasFiles = ref(false)

    const form = ref({
      name: '', background: '', question: '', rules: '',
      entity_count: 100, max_rounds: 5, start_year: 2026,
      darkness_base: 0, pressure_base: 0,
      stability_base: 50, hope_base: 50,
      time_unit: 'month', total_duration: 60, summary_interval: 6,
    })
    const ending = ref({
      bad_darkness: 90, bad_pressure: 95,
      good_hope: 85, good_stability: 60,
      bittersweet_hope: 40, bittersweet_darkness: 40,
      final_good_hope: 60, final_good_stability: 50,
      final_bad_darkness: 70, final_bad_pressure: 80,
      max_delta: 15,
    })
    const triggers = ref([])

    function metricColor(val, invert = false) {
      if (invert) {
        return val >= 60 ? '#27ae60' : val >= 30 ? '#e67e22' : '#e74c3c'
      }
      return val >= 70 ? '#e74c3c' : val >= 40 ? '#e67e22' : '#27ae60'
    }

    onMounted(async () => {
      if (scenarioId.value) {
        try {
          const data = await getScenario(scenarioId.value)
          Object.assign(form.value, data)
          hasFiles.value = (data.uploaded_files || []).length > 0
          if (data.ending_config) Object.assign(ending.value, data.ending_config)
          if (data.event_triggers) triggers.value = data.event_triggers
        } catch (e) {
          console.error('Failed to load scenario', e)
        }
      }
    })

    async function save() {
      saving.value = true
      try {
        await updateScenario(scenarioId.value, {
          ...form.value,
          ending_config: ending.value,
          event_triggers: triggers.value.filter(t => t.condition.trim()),
        })
      } finally {
        saving.value = false
      }
    }

    async function saveAndGenerate() {
      saving.value = true
      try {
        await updateScenario(scenarioId.value, {
          ...form.value,
          ending_config: ending.value,
          event_triggers: triggers.value.filter(t => t.condition.trim()),
        })
        router.push({ name: 'entities', params: { id: scenarioId.value } })
      } finally {
        saving.value = false
      }
    }

    function onFilesUploaded() {
      hasFiles.value = true
    }

    async function parseRulesFromFiles() {
      parsingRules.value = true
      try {
        const result = await parseRules(scenarioId.value)
        form.value.rules = result.rules
      } finally {
        parsingRules.value = false
      }
    }

    return {
      form, scenarioId, saving, parsingRules, hasFiles,
      ending, triggers, metricColor,
      save, saveAndGenerate, onFilesUploaded, parseRulesFromFiles,
    }
  },
}
</script>
