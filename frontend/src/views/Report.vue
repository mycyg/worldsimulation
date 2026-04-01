<template>
  <div class="ws-page">
    <div class="ws-section" v-if="!report && !loading">
      <h3>推演报告</h3>
      <p>推演尚未完成或报告未生成</p>
      <button class="ws-btn primary" @click="doGenerate" :disabled="generating">
        {{ generating ? '生成中...' : '生成报告' }}
      </button>
    </div>

    <div class="ws-section" v-if="loading">
      <p>加载中...</p>
    </div>

    <div class="ws-section report-section" v-if="report">
      <div class="ws-section-header">
        <div>
          <h3>推演报告</h3>
          <span class="ws-tag ending" :class="report.ending_type">
            {{ endingLabel(report.ending_type) }}
          </span>
        </div>
        <div class="ws-btn-row">
          <a class="ws-btn" :href="exportMd" download>导出 MD</a>
          <a class="ws-btn" :href="exportTxt" download>导出 TXT</a>
        </div>
      </div>
      <div class="report-content" v-html="renderedContent"></div>
    </div>
  </div>
</template>

<script>
import { ref, computed, onMounted } from 'vue'
import { getReport, generateReport, exportReport } from '../api.js'
import { marked } from 'marked'
import { useToast } from '../components/Toast.js'

marked.setOptions({ breaks: true, gfm: true })

export default {
  name: 'ReportView',
  props: { id: String },
  setup(props) {
    const { show: showToast } = useToast()
    const scenarioId = parseInt(props.id)
    const report = ref(null)
    const loading = ref(true)
    const generating = ref(false)

    const renderedContent = computed(() => {
      if (!report.value?.content) return ''
      const raw = marked.parse(report.value.content)
      // Basic XSS sanitization: strip script tags and event handlers
      return raw
        .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script>/gi, '')
        .replace(/\s*on\w+\s*=\s*("[^"]*"|'[^']*'|[^\s>]+)/gi, '')
    })

    const exportMd = computed(() => exportReport(scenarioId, 'md'))
    const exportTxt = computed(() => exportReport(scenarioId, 'txt'))

    onMounted(async () => {
      try {
        report.value = await getReport(scenarioId)
      } catch (e) {
        // Report not found, that's ok
      } finally {
        loading.value = false
      }
    })

    async function doGenerate() {
      generating.value = true
      try {
        report.value = await generateReport(scenarioId)
      } catch (e) {
        showToast('报告生成失败: ' + (e.response?.data?.error || e.message))
      } finally {
        generating.value = false
      }
    }

    function endingLabel(type) {
      const map = {
        good: 'Good End', bad: 'Bad End',
        bittersweet: 'Bittersweet End', neutral: 'Neutral End',
      }
      return map[type] || type
    }

    return { report, loading, generating, renderedContent, exportMd, exportTxt, doGenerate, endingLabel }
  },
}
</script>
