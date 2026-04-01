<template>
  <div class="ws-page sim-page">
    <!-- Metrics Bar -->
    <MetricsBar :metrics="currentMetrics" />

    <!-- Macro Indicators -->
    <div class="sim-macro-bar" v-if="macroIndicators && Object.keys(macroIndicators).length">
      <div class="sim-macro-item" v-for="(value, key) in macroIndicators" :key="key">
        <span class="sim-macro-name">{{ key }}</span>
        <span class="sim-macro-value">{{ value }}</span>
        <span class="sim-macro-trend" v-if="macroTrends[key]">
          <span :class="macroTrends[key] > 0 ? 'trend-up' : 'trend-down'">
            {{ macroTrends[key] > 0 ? '↑' : '↓' }}
          </span>
        </span>
      </div>
    </div>

    <!-- Main area -->
    <div class="sim-main">
      <!-- Left: Timeline -->
      <div class="sim-timeline-panel">
        <Timeline :events="timeline" />
      </div>

      <!-- Center: Chat-style round display -->
      <div class="sim-center">
        <div class="sim-status" v-if="simState.status === 'idle' || simState.status === 'draft'">
          <p>推演尚未开始</p>
          <button class="ws-btn primary" @click="start">开始推演</button>
        </div>

        <div class="sim-chat-area" v-else ref="chatArea">
          <!-- Round separator -->
          <div class="sim-round-separator" v-for="r in sortedRounds" :key="r.round">
            <div class="sim-round-badge">
              <span class="sim-round-badge-year">{{ r.tick_date || (r.year + '年') }}</span>
              <span class="sim-round-badge-num">Tick {{ r.round }}</span>
            </div>

            <!-- Situation card (narrator) -->
            <div class="sim-msg sim-msg-system" v-if="r.situation">
              <div class="sim-msg-avatar sim-avatar-narrator">叙</div>
              <div class="sim-msg-body">
                <div class="sim-msg-header">
                  <span class="sim-msg-name">局势旁白</span>
                  <span class="sim-msg-time">{{ r.tick_date || (r.year + '年') }}</span>
                </div>
                <div class="sim-msg-bubble sim-bubble-system">{{ r.situation }}</div>
              </div>
            </div>

            <!-- Phase 1: Proposals (legacy compat) -->
            <template v-if="r.proposals && r.proposals.length">
              <div class="sim-phase-marker">
                <span class="sim-phase-tag proposal">先行行动</span>
              </div>
              <div class="sim-msg" v-for="(p, pi) in r.proposals" :key="'p-'+pi"
                   :class="pi % 2 === 0 ? 'sim-msg-left' : 'sim-msg-right'">
                <div class="sim-msg-avatar" :style="{ background: getEntityColor(p.entity) }">
                  {{ (p.entity || '?')[0] }}
                </div>
                <div class="sim-msg-body">
                  <div class="sim-msg-header">
                    <span class="sim-msg-name">{{ p.entity }}</span>
                    <span class="sim-msg-tag sim-tag-proposal">{{ p.action_type === 'reactive' ? '反应' : '先行' }}</span>
                    <span class="sim-msg-time" v-if="p.timestamp">{{ p.timestamp }}</span>
                    <span class="sim-msg-tag" v-if="p.target">{{ p.target }}</span>
                  </div>
                  <div class="sim-msg-bubble">
                    <div class="sim-decision-thought" v-if="p.thought">{{ p.thought }}</div>
                    <div class="sim-decision-desire" v-if="p.desire"><span class="sim-desire-label">渴望</span> {{ p.desire }}</div>
                    <div class="sim-decision-fear" v-if="p.fear"><span class="sim-fear-label">恐惧</span> {{ p.fear }}</div>
                    <div class="sim-decision-action">{{ p.action }}</div>
                    <div class="sim-decision-outcome" v-if="p.expected_outcome">预期: {{ p.expected_outcome }}</div>
                  </div>
                </div>
              </div>
            </template>

            <!-- Phase 2: Reactions (legacy compat) -->
            <template v-if="r.reactions && r.reactions.length">
              <div class="sim-phase-marker">
                <span class="sim-phase-tag reaction">连锁反应</span>
              </div>
              <div class="sim-msg sim-msg-right" v-for="(rx, ri) in r.reactions" :key="'r-'+ri">
                <div class="sim-msg-avatar" :style="{ background: getEntityColor(rx.entity) }">
                  {{ (rx.entity || '?')[0] }}
                </div>
                <div class="sim-msg-body">
                  <div class="sim-msg-header">
                    <span class="sim-msg-name">{{ rx.entity }}</span>
                    <span class="sim-msg-tag sim-tag-reaction">反应</span>
                    <span class="sim-msg-time" v-if="rx.timestamp">{{ rx.timestamp }}</span>
                    <span class="sim-msg-tag" v-if="rx.reaction_to">→ {{ rx.reaction_to }}</span>
                  </div>
                  <div class="sim-msg-bubble">
                    <div class="sim-decision-thought" v-if="rx.thought">{{ rx.thought }}</div>
                    <div class="sim-decision-action">{{ rx.action }}</div>
                  </div>
                </div>
              </div>
            </template>

            <!-- Decision cards (entities) — legacy fallback -->
            <div class="sim-msg" v-for="(d, di) in r.decisions" :key="di"
                 :class="[di % 2 === 0 ? 'sim-msg-left' : 'sim-msg-right',
                           d.urgency === '紧迫' ? 'sim-msg-urgent' : '']">
              <div class="sim-msg-avatar" :style="{ background: getEntityColor(d.entity) }">
                {{ (d.entity || '?')[0] }}
              </div>
              <div class="sim-msg-body">
                <div class="sim-msg-header">
                  <span class="sim-msg-name">{{ d.entity }}</span>
                  <span class="sim-msg-tag sim-tag-urgency" v-if="d.urgency === '紧迫'">紧急</span>
                  <span class="sim-msg-tag" v-if="d.target">{{ d.target }}</span>
                </div>
                <div class="sim-msg-bubble">
                  <div class="sim-decision-thought" v-if="d.thought">{{ d.thought }}</div>
                  <div class="sim-decision-desire" v-if="d.desire"><span class="sim-desire-label">渴望</span> {{ d.desire }}</div>
                  <div class="sim-decision-fear" v-if="d.fear"><span class="sim-fear-label">恐惧</span> {{ d.fear }}</div>
                  <div class="sim-decision-action">{{ d.action }}</div>
                  <div class="sim-decision-outcome" v-if="d.expected_outcome">预期: {{ d.expected_outcome }}</div>
                </div>
                <!-- Action outcome from judge -->
                <div class="sim-action-result" v-if="getActionResult(r, d.entity)">
                  <span class="sim-result-label">结果:</span> {{ getActionResult(r, d.entity) }}
                </div>
              </div>
            </div>

            <!-- Major Event Highlight -->
            <div class="sim-msg sim-msg-major" v-if="r.majorEvent">
              <div class="sim-msg-avatar sim-avatar-major">!</div>
              <div class="sim-msg-body">
                <div class="sim-msg-header">
                  <span class="sim-msg-name sim-major-label">重大事件</span>
                  <span class="sim-msg-time">{{ r.tick_date || r.year + '年' }}</span>
                </div>
                <div class="sim-msg-bubble sim-bubble-major">{{ r.majorEvent }}</div>
              </div>
            </div>

            <!-- Summary card (periodic) -->
            <div class="sim-msg sim-msg-summary" v-if="r.summaryText">
              <div class="sim-msg-avatar sim-avatar-summary">总</div>
              <div class="sim-msg-body">
                <div class="sim-msg-header">
                  <span class="sim-msg-name">阶段总结</span>
                  <span class="sim-msg-time">{{ r.tick_date || '' }}</span>
                </div>
                <div class="sim-msg-bubble sim-bubble-summary">{{ r.summaryText }}</div>
              </div>
            </div>

            <!-- Resolution card (judge) -->
            <div class="sim-msg sim-msg-judge" v-if="r.resolution">
              <div class="sim-msg-avatar sim-avatar-judge">裁</div>
              <div class="sim-msg-body">
                <div class="sim-msg-header">
                  <span class="sim-msg-name">推演裁判</span>
                  <span class="sim-msg-time">结果</span>
                </div>
                <div class="sim-msg-bubble sim-bubble-judge">{{ r.resolution }}</div>
              </div>
            </div>

            <!-- Metrics snapshot -->
            <div class="sim-metrics-snippet" v-if="r.metrics">
              <span class="sim-metric-chip" style="--mc: var(--dark)">D {{ r.metrics.darkness }}</span>
              <span class="sim-metric-chip" style="--mc: var(--pressure)">P {{ r.metrics.pressure }}</span>
              <span class="sim-metric-chip" style="--mc: var(--stability)">S {{ r.metrics.stability }}</span>
              <span class="sim-metric-chip" style="--mc: var(--hope)">H {{ r.metrics.hope }}</span>
            </div>
          </div>

          <!-- Injected events -->
          <div class="sim-msg sim-msg-injected" v-for="(evt, ei) in injectedEvents" :key="'inj-'+ei">
            <div class="sim-msg-avatar sim-avatar-injected">!</div>
            <div class="sim-msg-body">
              <div class="sim-msg-header">
                <span class="sim-msg-name">外部事件</span>
                <span class="sim-msg-time">{{ evt.year }} 年</span>
              </div>
              <div class="sim-msg-bubble sim-bubble-injected">{{ evt.content }}</div>
            </div>
          </div>

          <!-- Spawned entities -->
          <div class="sim-msg sim-msg-spawned" v-for="(sp, si) in spawnedEntities" :key="'sp-'+si">
            <div class="sim-msg-avatar sim-avatar-spawned">新</div>
            <div class="sim-msg-body">
              <div class="sim-msg-header">
                <span class="sim-msg-name">新实体涌现</span>
                <span class="sim-msg-time">{{ sp.year }} 年</span>
              </div>
              <div class="sim-msg-bubble sim-bubble-spawned">
                <strong>{{ sp.entity?.name }}</strong> ({{ sp.entity?.type }}) — {{ sp.reason }}
              </div>
            </div>
          </div>

          <!-- Ending card -->
          <div class="sim-ending-card" v-if="ending">
            <div class="sim-ending-badge" :class="ending.type">{{ endingLabel(ending.type) }}</div>
            <div class="sim-ending-text">{{ ending.description }}</div>
            <div class="sim-ending-metrics" v-if="ending.metrics">
              <span>黑暗 {{ ending.metrics.darkness }}</span>
              <span>压力 {{ ending.metrics.pressure }}</span>
              <span>稳定 {{ ending.metrics.stability }}</span>
              <span>希望 {{ ending.metrics.hope }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Controls -->
      <div class="sim-controls-panel">
        <SimControls
          :status="simState.status"
          :scenario-id="scenarioId"
          @start="start"
          @pause="pause"
          @resume="resume"
          @stop="stop"
          @inject="inject"
          @reset="resetSimFn"
          :key="simState.status"
        />

        <div class="sim-entity-panel" v-if="allEntities.length">
          <h4>实体压力</h4>
          <div class="sim-entity-pressure-item" v-for="e in sortedEntities" :key="e.id">
            <div class="sim-entity-pressure-header">
              <span class="sim-entity-pressure-name">{{ e.name }}</span>
              <span class="ws-tag" :class="e.status || 'active'">{{ statusLabel(e.status) }}</span>
            </div>
            <div class="sim-entity-pressure-bar">
              <div class="sim-entity-pressure-fill" :class="pressureClass(e.pressure)"
                   :style="{ width: Math.min(100, Math.max(0, e.pressure)) + '%' }"></div>
            </div>
            <div class="sim-entity-pressure-info">
              <span class="sim-entity-pressure-val">{{ Math.round(e.pressure) }}</span>
              <span class="sim-entity-influence" v-if="e.influence != null"
                    :class="e.influence >= 70 ? 'high' : e.influence >= 40 ? 'mid' : 'low'">
                影响力 {{ Math.round(e.influence) }}
              </span>
              <span class="sim-entity-pressure-faction" v-if="e.faction">{{ e.faction }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom: Knowledge Graph (collapsible) -->
    <div class="sim-bottom">
      <div class="sim-bottom-toggle" @click="showGraph = !showGraph">
        <span>知识图谱</span>
        <span class="sim-bottom-toggle-icon">{{ showGraph ? '▲' : '▼' }}</span>
      </div>
      <div class="sim-graph-wrap" v-if="showGraph">
        <GraphPanel :scenario-id="scenarioId" />
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive, onMounted, onUnmounted, nextTick, computed } from 'vue'
import { io } from 'socket.io-client'
import { getSimState, getTimeline, getRounds, startSim, pauseSim, resumeSim, stopSim, resetSim, injectEvent, listEntities } from '../api.js'
import MetricsBar from '../components/MetricsBar.vue'
import Timeline from '../components/Timeline.vue'
import SimControls from '../components/SimControls.vue'
import GraphPanel from '../components/GraphPanel.vue'
import { useToast } from '../components/Toast.js'

const ENTITY_COLORS = [
  '#FF6B35','#004E89','#7B2D8E','#1A936F','#C5283D',
  '#E9724C','#3498db','#9b59b6','#27ae60','#f39c12',
]
const colorCache = {}
let colorIdx = 0

export default {
  name: 'SimulationView',
  components: { MetricsBar, Timeline, SimControls, GraphPanel },
  props: { id: String },
  setup(props) {
    const { show: showToast } = useToast()
    const scenarioId = parseInt(props.id)
    const simState = ref({ status: 'idle', current_round: 0, max_rounds: 5, current_year: 2026 })
    const currentMetrics = ref({ darkness: 0, pressure: 0, stability: 50, hope: 50 })
    const timeline = ref([])
    const activeEntities = ref([])
    const allEntities = ref([])
    const ending = ref(null)
    const chatArea = ref(null)
    const showGraph = ref(false)

    // Structured round data for chat display
    const roundMessages = reactive({})
    const injectedEvents = reactive([])
    const spawnedEntities = reactive([])
    const macroIndicators = ref({})
    const prevMacroIndicators = ref({})
    const macroTrends = computed(() => {
      const trends = {}
      for (const key of Object.keys(macroIndicators.value)) {
        const prev = prevMacroIndicators.value[key]
        if (prev != null && typeof prev === 'number') {
          trends[key] = macroIndicators.value[key] - prev
        }
      }
      return trends
    })

    let socket = null

    function getEntityColor(name) {
      if (!colorCache[name]) {
        colorCache[name] = ENTITY_COLORS[colorIdx % ENTITY_COLORS.length]
        colorIdx++
      }
      return colorCache[name]
    }

    function ensureRound(round, year, date) {
      if (!roundMessages[round]) {
        roundMessages[round] = { round, year, tick_date: '', situation: '', decisions: [], proposals: [], reactions: [], resolution: '', actionOutcomes: [], metrics: null }
      }
      if (year) roundMessages[round].year = year
      if (date) roundMessages[round].tick_date = date
      return roundMessages[round]
    }

    function getActionResult(r, entityName) {
      if (!r.actionOutcomes || !entityName) return ''
      const outcome = r.actionOutcomes.find(o => o.entity === entityName)
      return outcome ? `${outcome.result} ${outcome.impact || ''}` : ''
    }

    function scrollToBottom() {
      nextTick(() => {
        if (chatArea.value) {
          chatArea.value.scrollTop = chatArea.value.scrollHeight
        }
      })
    }

    onMounted(async () => {
      // Load entities for pressure panel
      try {
        const entityData = await listEntities(scenarioId)
        // Flatten factions → flat array
        const flat = []
        if (entityData.factions) {
          for (const ents of Object.values(entityData.factions)) {
            flat.push(...ents)
          }
        }
        allEntities.value = flat
      } catch (e) { /* ignore */ }

      try {
        const state = await getSimState(scenarioId)
        Object.assign(simState.value, state)
        if (state.metrics && state.metrics.length) {
          currentMetrics.value = state.metrics[0]
        }
      } catch (e) { /* scenario may not have started yet */ }

      // Load rounds with decisions from API
      try {
        const rounds = await getRounds(scenarioId)
        for (const rd of rounds) {
          const r = ensureRound(rd.round, rd.year)
          if (rd.situation) r.situation = rd.situation
          if (rd.decisions && rd.decisions.length) r.decisions = rd.decisions
          if (rd.resolution) r.resolution = rd.resolution
          if (rd.metrics) r.metrics = rd.metrics
          // Load phased data
          if (rd.phases) {
            if (rd.phases.proposals && rd.phases.proposals.length) r.proposals = rd.phases.proposals
            if (rd.phases.reactions && rd.phases.reactions.length) r.reactions = rd.phases.reactions
          }
          if (rd.macro_indicators && Object.keys(rd.macro_indicators).length) {
            prevMacroIndicators.value = { ...macroIndicators.value }
            macroIndicators.value = rd.macro_indicators
          }
        }
      } catch (e) { /* ignore */ }

      // Load injected events from timeline
      try {
        timeline.value = await getTimeline(scenarioId)
        for (const evt of timeline.value) {
          if (evt.type === 'injected') {
            injectedEvents.push({ content: evt.content, year: evt.year })
          }
        }
      } catch (e) { /* ignore */ }

      // Connect SocketIO
      socket = io({ transports: ['websocket', 'polling'] })
      socket.on('connect', () => {
        socket.emit('join_scenario', { scenario_id: scenarioId })
      })
      socket.on('sim:progress', (data) => {
        if (data.status) simState.value.status = data.status
      })
      socket.on('sim:round', (data) => {
        const round = data.round ?? data.tick ?? 0
        const year = data.year ?? 0
        const date = data.date || data.tick_date || ''

        if (data.status === 'running') {
          simState.value.current_round = round
          simState.value.current_year = year
          return
        }

        if (data.type === 'injected') {
          injectedEvents.push({ content: data.content, year: data.year })
          timeline.value.push(data)
          scrollToBottom()
          return
        }

        // Round result
        const r = ensureRound(round, year, date)
        if (data.situation) {
          r.situation = data.situation
        }
        if (data.date || data.tick_date) {
          r.tick_date = data.date || data.tick_date
        }
        if (data.major_event) {
          r.majorEvent = data.major_event
        }
        if (data.summary) {
          r.resolution = data.summary
        }
        if (data.decisions && data.decisions.length) {
          r.decisions = data.decisions
        }
        if (data.proposals && data.proposals.length) {
          r.proposals = data.proposals
        }
        if (data.reactions && data.reactions.length) {
          r.reactions = data.reactions
        }
        if (data.action_outcomes && data.action_outcomes.length) {
          r.actionOutcomes = data.action_outcomes
        }
        if (data.active_entities) {
          activeEntities.value = data.active_entities
          for (const ae of data.active_entities) {
            const ent = allEntities.value.find(e => e.name === ae.name)
            if (ent) {
              if (ae.status) ent.status = ae.status
              if (ae.pressure != null) ent.pressure = ae.pressure
              if (ae.faction) ent.faction = ae.faction
              if (ae.influence != null) ent.influence = ae.influence
            }
          }
        }
        if (data.year) simState.value.current_year = data.year
        if (data.round != null) simState.value.current_round = data.round

        if (data.macro_indicators) {
          prevMacroIndicators.value = { ...macroIndicators.value }
          macroIndicators.value = data.macro_indicators
        }

        if (data.content) {
          timeline.value.push(data)
        } else if (data.summary) {
          timeline.value.push({
            type: 'narrative', content: data.summary,
            year: data.year, round: data.round,
          })
        }

        scrollToBottom()
      })
      socket.on('sim:metrics', (data) => {
        currentMetrics.value = data
        const round = simState.value.current_round
        if (roundMessages[round]) {
          roundMessages[round].metrics = { ...data }
        }
      })
      socket.on('sim:phase', (data) => {
        const r = ensureRound(data.round, data.year, data.date)
        r.phaseLabel = data.label
        r.currentPhase = data.phase
      })
      socket.on('sim:entity_spawned', (data) => {
        spawnedEntities.push(data)
        if (data.entity) {
          allEntities.value.push({
            id: Date.now(),
            name: data.entity.name,
            type: data.entity.type,
            faction: data.entity.faction,
            description: data.entity.description,
            pressure: 50,
            influence: 40,
            status: 'active',
          })
        }
        scrollToBottom()
      })
      socket.on('sim:summary', (data) => {
        const r = ensureRound(data.tick || 0, null, data.date)
        r.summaryText = data.summary
        scrollToBottom()
      })
      socket.on('sim:ending', (data) => {
        ending.value = data
        simState.value.status = 'done'
        scrollToBottom()
      })
      socket.on('sim:error', (data) => {
        showToast('推演错误: ' + data.error)
      })
    })

    onUnmounted(() => {
      if (socket) socket.disconnect()
    })

    async function start() {
      await startSim(scenarioId)
      simState.value.status = 'running'
    }
    async function pause() {
      await pauseSim(scenarioId)
      simState.value.status = 'paused'
    }
    async function resume() {
      await resumeSim(scenarioId)
      simState.value.status = 'running'
    }
    async function stop() {
      await stopSim(scenarioId)
      simState.value.status = 'ready'
    }
    async function inject(event) {
      await injectEvent(scenarioId, event)
    }

    async function resetSimFn() {
      await resetSim(scenarioId)
      Object.keys(roundMessages).forEach(k => delete roundMessages[k])
      injectedEvents.splice(0)
      spawnedEntities.splice(0)
      ending.value = null
      timeline.value = []
      macroIndicators.value = {}
      prevMacroIndicators.value = {}
      simState.value = { status: 'ready', current_round: 0, max_rounds: simState.value.max_rounds, current_year: simState.value.start_year || 2026 }
      currentMetrics.value = { darkness: 0, pressure: 0, stability: 50, hope: 50 }
      const entityData = await listEntities(scenarioId)
      const flat = []
      if (entityData.factions) {
        for (const ents of Object.values(entityData.factions)) {
          flat.push(...ents)
        }
      }
      allEntities.value = flat
    }

    const sortedEntities = computed(() => {
      return [...allEntities.value].sort((a, b) => (b.influence || 0) - (a.influence || 0))
    })

    function pressureClass(p) {
      if (p >= 90) return 'critical'
      if (p >= 70) return 'high'
      if (p >= 40) return 'medium'
      return 'low'
    }

    function statusLabel(s) {
      const map = { active: '活跃', weakened: '削弱', empowered: '增强', transformed: '蜕变', dead: '消亡' }
      return map[s] || s || '活跃'
    }

    function endingLabel(type) {
      const map = {
        good: 'Good End - 曙光初现',
        bad: 'Bad End - 黑暗降临',
        bittersweet: 'Bittersweet End - 苦乐参半',
        neutral: 'Neutral End - 未完之局',
      }
      return map[type] || type
    }

    const sortedRounds = computed(() => {
      return Object.keys(roundMessages)
        .map(Number)
        .sort((a, b) => a - b)
        .map(k => roundMessages[k])
    })
    return {
      scenarioId, simState, currentMetrics, timeline,
      roundMessages, sortedRounds, injectedEvents, spawnedEntities, activeEntities, allEntities, ending,
      macroIndicators, prevMacroIndicators, macroTrends,
      chatArea, showGraph, getEntityColor, getActionResult, endingLabel,
      sortedEntities, pressureClass, statusLabel,
      start, pause, resume, stop, inject, resetSim: resetSimFn,
    }
  },
}
</script>
