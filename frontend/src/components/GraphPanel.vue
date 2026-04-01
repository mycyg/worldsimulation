<template>
  <div class="ws-graph-panel" :class="{ 'ws-graph-fullscreen': isFullscreen }">
    <div class="ws-graph-header">
      <h4>知识图谱</h4>
      <div class="ws-graph-controls">
        <input v-model="searchQuery" placeholder="搜索图谱..." @keyup.enter="doSearch" />
        <button class="ws-btn" @click="doSearch" :disabled="!searchQuery.trim()">搜索</button>
        <button class="ws-btn" @click="fetchGraph">刷新</button>
        <label class="ws-toggle-label">
          <input type="checkbox" v-model="showEdgeLabels" />
          <span>标签</span>
        </label>
        <button class="ws-btn" @click="toggleFullscreen">{{ isFullscreen ? '退出全屏' : '全屏' }}</button>
      </div>
    </div>

    <div class="ws-graph-stats" v-if="graphData.nodes.length">
      <span class="ws-tag">{{ graphData.nodes.length }} 节点</span>
      <span class="ws-tag">{{ graphData.edges.length }} 关系</span>
    </div>

    <div class="ws-graph-empty" v-if="!graphData.nodes.length && !loading">
      <p>暂无图谱数据。推演开始后将自动构建知识图谱。</p>
    </div>

    <div class="ws-graph-loading" v-if="loading">
      <span>加载中...</span>
    </div>

    <div class="ws-graph-canvas" ref="canvas"></div>

    <!-- Entity type legend -->
    <div class="ws-graph-legend" v-if="entityTypes.length">
      <span class="ws-graph-legend-title">实体类型</span>
      <div class="ws-graph-legend-items">
        <div class="ws-graph-legend-item" v-for="t in entityTypes" :key="t.name">
          <span class="ws-graph-legend-dot" :style="{ background: t.color }"></span>
          <span>{{ t.name }}</span>
        </div>
      </div>
    </div>

    <!-- Detail panel for selected node/edge -->
    <div class="ws-graph-detail" v-if="selectedItem">
      <div class="ws-graph-detail-header">
        <span class="ws-graph-detail-title">{{ selectedItem.type === 'node' ? '节点详情' : '关系详情' }}</span>
        <span v-if="selectedItem.entityType" class="ws-tag" :style="{ background: selectedItem.color }">{{ selectedItem.entityType }}</span>
        <button class="ws-graph-detail-close" @click="selectedItem = null">&times;</button>
      </div>
      <div class="ws-graph-detail-body">
        <template v-if="selectedItem.type === 'node'">
          <div class="ws-graph-detail-row" v-if="selectedItem.data.name">
            <span class="ws-graph-detail-label">名称</span>
            <span>{{ selectedItem.data.name }}</span>
          </div>
          <div class="ws-graph-detail-row" v-if="selectedItem.data.faction">
            <span class="ws-graph-detail-label">阵营</span>
            <span>{{ selectedItem.data.faction }}</span>
          </div>
          <div class="ws-graph-detail-row" v-if="selectedItem.data.summary">
            <span class="ws-graph-detail-label">简介</span>
            <span>{{ selectedItem.data.summary }}</span>
          </div>
        </template>
        <template v-else>
          <div class="ws-graph-detail-row" v-if="selectedItem.data.sourceName">
            <span class="ws-graph-detail-label">源</span>
            <span>{{ selectedItem.data.sourceName }}</span>
          </div>
          <div class="ws-graph-detail-row" v-if="selectedItem.data.targetName">
            <span class="ws-graph-detail-label">目标</span>
            <span>{{ selectedItem.data.targetName }}</span>
          </div>
          <div class="ws-graph-detail-row" v-if="selectedItem.data.fact">
            <span class="ws-graph-detail-label">关系</span>
            <span>{{ selectedItem.data.fact }}</span>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted, onUnmounted, watch, nextTick } from 'vue'
import * as d3 from 'd3'
import { getGraphData, searchGraph } from '../api.js'

const PALETTE = ['#FF6B35','#004E89','#7B2D8E','#1A936F','#C5283D','#E9724C','#3498db','#9b59b6','#27ae60','#f39c12']

export default {
  name: 'GraphPanel',
  props: {
    scenarioId: { type: Number, required: true },
  },
  setup(props) {
    const canvas = ref(null)
    const graphData = ref({ nodes: [], edges: [], communities: [] })
    const loading = ref(false)
    const searchQuery = ref('')
    const isFullscreen = ref(false)
    const showEdgeLabels = ref(true)
    const selectedItem = ref(null)

    let simulation = null
    let svg = null
    let resizeObserver = null
    let linkLabelsRef = null
    let linkLabelBgRef = null

    const entityTypes = computed(() => {
      const typeMap = {}
      graphData.value.nodes.forEach(n => {
        const t = n.type || 'Entity'
        if (!typeMap[t]) typeMap[t] = { name: t, count: 0, color: PALETTE[Object.keys(typeMap).length % PALETTE.length] }
        typeMap[t].count++
      })
      return Object.values(typeMap)
    })

    onMounted(() => {
      fetchGraph()
      resizeObserver = new ResizeObserver(() => {
        if (graphData.value.nodes.length) renderGraph()
      })
      if (canvas.value) resizeObserver.observe(canvas.value)
    })

    onUnmounted(() => {
      if (simulation) simulation.stop()
      if (resizeObserver) resizeObserver.disconnect()
    })

    watch(showEdgeLabels, (v) => {
      if (linkLabelsRef) linkLabelsRef.style('display', v ? 'block' : 'none')
      if (linkLabelBgRef) linkLabelBgRef.style('display', v ? 'block' : 'none')
    })

    async function fetchGraph() {
      loading.value = true
      try {
        graphData.value = await getGraphData(props.scenarioId)
        await nextTick()
        if (graphData.value.nodes.length) renderGraph()
      } catch (e) {
        console.error('Graph fetch error:', e)
      } finally {
        loading.value = false
      }
    }

    async function doSearch() {
      if (!searchQuery.value.trim()) return
      loading.value = true
      try {
        const results = await searchGraph(props.scenarioId, searchQuery.value)
        const nodes = results.nodes.map(n => ({ ...n, highlighted: true }))
        const edges = results.edges.map(e => ({ ...e, highlighted: true }))
        graphData.value = { nodes, edges, communities: [] }
        await nextTick()
        if (nodes.length) renderGraph()
      } catch (e) {
        console.error('Graph search error:', e)
      } finally {
        loading.value = false
      }
    }

    function renderGraph() {
      if (!canvas.value) return
      if (simulation) simulation.stop()

      d3.select(canvas.value).selectAll('*').remove()

      const containerW = canvas.value.clientWidth || 600
      const containerH = Math.max(400, canvas.value.clientHeight || 400)

      svg = d3.select(canvas.value)
        .append('svg')
        .attr('width', containerW)
        .attr('height', containerH)
        .attr('viewBox', `0 0 ${containerW} ${containerH}`)

      const data = graphData.value
      if (!data.nodes.length) return

      // Build color map
      const colorMap = {}
      entityTypes.value.forEach(t => colorMap[t.name] = t.color)
      const getColor = (type) => colorMap[type] || '#999'

      // Build links from edges
      const nodeIds = new Set(data.nodes.map(n => n.id))
      const links = data.edges.filter(e =>
        nodeIds.has(e.source) && nodeIds.has(e.target)
      ).map(e => ({
        source: e.source,
        target: e.target,
        fact: e.fact || '',
        id: e.id,
        highlighted: e.highlighted,
        sourceName: e.sourceName || '',
        targetName: e.targetName || '',
      }))

      // Count edges per pair for curvature
      const pairCount = {}
      const pairIndex = {}
      links.forEach(l => {
        if (l.source === l.target) return
        const key = [l.source, l.target].sort().join('_')
        pairCount[key] = (pairCount[key] || 0) + 1
      })

      links.forEach((l, i) => {
        if (l.source === l.target) { l.curvature = 0; return }
        const key = [l.source, l.target].sort().join('_')
        const total = pairCount[key] || 1
        const idx = pairIndex[key] || 0
        pairIndex[key] = idx + 1
        const isReversed = l.source > l.target
        if (total <= 1) { l.curvature = 0; return }
        const range = Math.min(1.2, 0.6 + total * 0.15)
        l.curvature = ((idx / (total - 1)) - 0.5) * range * 2 * (isReversed ? -1 : 1)
      })

      const n = data.nodes.length
      const sim = d3.forceSimulation(data.nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(d => 120 + (pairCount[[d.source.id, d.target.id].sort().join('_')] || 1) * 30))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(containerW / 2, containerH / 2))
        .force('collision', d3.forceCollide(30))
        .force('x', d3.forceX(containerW / 2).strength(0.04))
        .force('y', d3.forceY(containerH / 2).strength(0.04))
      simulation = sim

      const g = svg.append('g')

      // Zoom
      const zoom = d3.zoom().scaleExtent([0.1, 6]).on('zoom', (event) => {
        g.attr('transform', event.transform)
      })
      svg.call(zoom)

      // Click background to deselect
      svg.on('click', () => {
        selectedItem.value = null
        resetHighlight()
      })

      // Link paths
      const getLinkPath = (d) => {
        const sx = d.source.x, sy = d.source.y
        const tx = d.target.x, ty = d.target.y
        if (d.source === d.target) {
          const r = 25
          return `M${sx+8},${sy-4} A${r},${r} 0 1,1 ${sx+8},${sy+4}`
        }
        if (d.curvature === 0) return `M${sx},${sy} L${tx},${ty}`
        const dx = tx - sx, dy = ty - sy
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const off = Math.max(30, dist * 0.25) * d.curvature
        const cx = (sx + tx) / 2 + (-dy / dist) * off
        const cy = (sy + ty) / 2 + (dx / dist) * off
        return `M${sx},${sy} Q${cx},${cy} ${tx},${ty}`
      }

      const getLinkMid = (d) => {
        const sx = d.source.x, sy = d.source.y, tx = d.target.x, ty = d.target.y
        if (d.source === d.target) return { x: sx + 60, y: sy }
        if (d.curvature === 0) return { x: (sx + tx) / 2, y: (sy + ty) / 2 }
        const dx = tx - sx, dy = ty - sy, dist = Math.sqrt(dx * dx + dy * dy) || 1
        const off = Math.max(30, dist * 0.25) * d.curvature
        const cx = (sx + tx) / 2 + (-dy / dist) * off
        const cy = (sy + ty) / 2 + (dx / dist) * off
        return { x: 0.25 * sx + 0.5 * cx + 0.25 * tx, y: 0.25 * sy + 0.5 * cy + 0.25 * ty }
      }

      // Draw links
      const linkGroup = g.append('g')
      const link = linkGroup.selectAll('path')
        .data(links)
        .join('path')
        .attr('stroke', d => d.highlighted ? '#ff6b6b' : '#666')
        .attr('stroke-width', 1.5)
        .attr('fill', 'none')
        .attr('stroke-opacity', 0.6)
        .style('cursor', 'pointer')
        .on('click', (event, d) => {
          event.stopPropagation()
          resetHighlight()
          d3.select(event.target).attr('stroke', '#3498db').attr('stroke-width', 3)
          selectedItem.value = {
            type: 'edge',
            data: { sourceName: d.sourceName || d.source.name, targetName: d.targetName || d.target.name, fact: d.fact }
          }
        })

      // Edge label backgrounds
      const linkLabelBg = linkGroup.selectAll('rect')
        .data(links.filter(l => l.fact && l.fact.length < 30))
        .join('rect')
        .attr('fill', 'rgba(20,20,40,0.85)')
        .attr('rx', 3)
        .attr('stroke', '#333')
        .attr('stroke-width', 0.5)
        .style('pointer-events', 'all')
        .style('cursor', 'pointer')
        .style('display', showEdgeLabels.value ? 'block' : 'none')

      // Edge labels
      const linkLabels = linkGroup.selectAll('text.edge-label')
        .data(links.filter(l => l.fact && l.fact.length < 30))
        .join('text')
        .attr('class', 'edge-label')
        .text(d => d.fact.length > 15 ? d.fact.substring(0, 14) + '..' : d.fact)
        .attr('font-size', '9px')
        .attr('fill', '#aaa')
        .attr('text-anchor', 'middle')
        .attr('dominant-baseline', 'middle')
        .style('pointer-events', 'all')
        .style('cursor', 'pointer')
        .style('display', showEdgeLabels.value ? 'block' : 'none')

      linkLabelsRef = linkLabels
      linkLabelBgRef = linkLabelBg

      // Draw nodes
      const nodeGroup = g.append('g')
      const node = nodeGroup.selectAll('g')
        .data(data.nodes)
        .join('g')
        .style('cursor', 'pointer')
        .call(d3.drag()
          .on('start', (event, d) => {
            if (!event.active) sim.alphaTarget(0.3).restart()
            d.fx = d.x; d.fy = d.y
          })
          .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y })
          .on('end', (event, d) => {
            if (!event.active) sim.alphaTarget(0)
            d.fx = null; d.fy = null
          }))

      const r = n > 60 ? 5 : n > 30 ? 7 : 10
      node.append('circle')
        .attr('r', d => d.highlighted ? r + 3 : r)
        .attr('fill', d => getColor(d.type))
        .attr('stroke', d => d.highlighted ? '#ff6b6b' : '#fff')
        .attr('stroke-width', 2)

      // Node labels
      if (n <= 60) {
        node.append('text')
          .text(d => {
            const name = d.name || ''
            const maxLen = n > 30 ? 5 : 8
            return name.length > maxLen ? name.substring(0, maxLen - 1) + '..' : name
          })
          .attr('dx', r + 4)
          .attr('dy', 4)
          .attr('font-size', n > 30 ? '9px' : '11px')
          .attr('fill', '#ddd')
          .style('pointer-events', 'none')
      }

      // Node click - highlight connected edges
      node.on('click', (event, d) => {
        event.stopPropagation()
        resetHighlight()
        // Highlight this node
        d3.select(event.currentTarget).select('circle').attr('stroke', '#E91E63').attr('stroke-width', 4)
        // Highlight connected edges
        link.filter(l => l.source.id === d.id || l.target.id === d.id)
          .attr('stroke', '#E91E63').attr('stroke-width', 2.5).attr('stroke-opacity', 1)
        // Dim other nodes
        node.filter(n => n.id !== d.id).select('circle').attr('stroke-opacity', 0.3)
        node.filter(n => {
          const connected = links.some(l =>
            (l.source.id === d.id && l.target.id === n.id) ||
            (l.target.id === d.id && l.source.id === n.id)
          )
          return !connected && n.id !== d.id
        }).select('circle').attr('fill-opacity', 0.2)

        selectedItem.value = {
          type: 'node',
          data: d,
          entityType: d.type,
          color: getColor(d.type)
        }
      })

      function resetHighlight() {
        node.select('circle').attr('stroke', d => d.highlighted ? '#ff6b6b' : '#fff')
          .attr('stroke-width', 2).attr('stroke-opacity', 1).attr('fill-opacity', 1)
        link.attr('stroke', d => d.highlighted ? '#ff6b6b' : '#666')
          .attr('stroke-width', 1.5).attr('stroke-opacity', 0.6)
      }

      // Tick
      sim.on('tick', () => {
        link.attr('d', getLinkPath)
        linkLabels.each(function(d) {
          const mid = getLinkMid(d)
          d3.select(this).attr('x', mid.x).attr('y', mid.y)
        })
        linkLabelBg.each(function(d, i) {
          const mid = getLinkMid(d)
          const textEl = linkLabels.nodes()[i]
          if (textEl) {
            const bbox = textEl.getBBox()
            d3.select(this)
              .attr('x', mid.x - bbox.width / 2 - 4)
              .attr('y', mid.y - bbox.height / 2 - 2)
              .attr('width', bbox.width + 8)
              .attr('height', bbox.height + 4)
          }
        })
        node.attr('transform', d => `translate(${d.x},${d.y})`)
      })

      // Auto-fit after settle
      sim.on('end', () => {
        const xs = data.nodes.map(d => d.x), ys = data.nodes.map(d => d.y)
        const bw = Math.max(...xs) - Math.min(...xs) + 80
        const bh = Math.max(...ys) - Math.min(...ys) + 80
        const scale = Math.min(containerW / bw, containerH / bh, 2) * 0.85
        const cx = (Math.min(...xs) + Math.max(...xs)) / 2
        const cy = (Math.min(...ys) + Math.max(...ys)) / 2
        svg.transition().duration(500).call(
          zoom.transform,
          d3.zoomIdentity.translate(containerW / 2 - scale * cx, containerH / 2 - scale * cy).scale(scale)
        )
      })
    }

    function toggleFullscreen() {
      isFullscreen.value = !isFullscreen.value
      nextTick(() => {
        if (graphData.value.nodes.length) renderGraph()
      })
    }

    return {
      canvas, graphData, loading, searchQuery, isFullscreen,
      showEdgeLabels, selectedItem, entityTypes,
      toggleFullscreen, fetchGraph, doSearch,
    }
  },
}
</script>

<style scoped>
.ws-graph-panel {
  background: #1a1a2e;
  border: 1px solid #333;
  border-radius: 8px;
  padding: 12px;
  margin-top: 12px;
  position: relative;
}

.ws-graph-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.ws-graph-header h4 { margin: 0; color: #eee; }

.ws-graph-controls {
  display: flex;
  gap: 6px;
  align-items: center;
}

.ws-graph-controls input {
  background: #2a2a3e;
  border: 1px solid #444;
  color: #ddd;
  padding: 4px 8px;
  border-radius: 4px;
  width: 140px;
  font-size: 12px;
}

.ws-graph-controls .ws-btn {
  font-size: 12px;
  padding: 4px 10px;
}

.ws-toggle-label {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #aaa;
  cursor: pointer;
}

.ws-toggle-label input { cursor: pointer; }

.ws-graph-stats {
  display: flex;
  gap: 6px;
  margin-bottom: 8px;
}

.ws-graph-stats .ws-tag {
  background: #2a2a3e;
  color: #aaa;
  font-size: 11px;
}

.ws-graph-empty { text-align: center; color: #666; padding: 40px 0; }
.ws-graph-loading { text-align: center; color: #888; padding: 20px 0; }

.ws-graph-canvas {
  width: 100%;
  height: 100%;
  min-height: 400px;
  background: #0d0d1a;
  border-radius: 6px;
  overflow: hidden;
  position: relative;
}

.ws-graph-canvas :deep(svg) { display: block; }

/* Legend */
.ws-graph-legend {
  position: absolute;
  bottom: 24px;
  left: 24px;
  background: rgba(26,26,46,0.92);
  padding: 10px 14px;
  border-radius: 8px;
  border: 1px solid #333;
  z-index: 10;
}

.ws-graph-legend-title {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: #E91E63;
  margin-bottom: 8px;
}

.ws-graph-legend-items {
  display: flex;
  flex-wrap: wrap;
  gap: 8px 14px;
  max-width: 300px;
}

.ws-graph-legend-item {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: #ccc;
}

.ws-graph-legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

/* Detail panel */
.ws-graph-detail {
  position: absolute;
  top: 60px;
  right: 16px;
  width: 260px;
  background: rgba(26,26,46,0.95);
  border: 1px solid #444;
  border-radius: 8px;
  z-index: 20;
  overflow: hidden;
}

.ws-graph-detail-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid #333;
  background: rgba(0,0,0,0.2);
}

.ws-graph-detail-title { font-size: 13px; font-weight: 600; color: #eee; }

.ws-graph-detail-close {
  background: none;
  border: none;
  color: #888;
  font-size: 18px;
  cursor: pointer;
  padding: 0 4px;
}

.ws-graph-detail-close:hover { color: #fff; }

.ws-graph-detail-body { padding: 12px; }

.ws-graph-detail-row {
  margin-bottom: 8px;
  font-size: 12px;
  color: #ccc;
}

.ws-graph-detail-label {
  display: block;
  font-size: 10px;
  color: #888;
  text-transform: uppercase;
  margin-bottom: 2px;
}

/* Fullscreen */
.ws-graph-fullscreen {
  position: fixed;
  inset: 0;
  z-index: 200;
  margin: 0;
  border-radius: 0;
  display: flex;
  flex-direction: column;
}

.ws-graph-fullscreen .ws-graph-canvas {
  flex: 1;
  height: auto;
  min-height: 0;
}
</style>
