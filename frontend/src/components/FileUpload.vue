<template>
  <div class="ws-upload" @dragover.prevent @drop.prevent="onDrop">
    <div class="ws-upload-zone" :class="{ dragging }"
      @dragenter="dragging = true" @dragleave="dragging = false"
      @drop="onDrop" @click="$refs.fileInput.click()">
      <p v-if="!uploading">
        拖拽文件到此处，或点击选择<br>
        <small>支持 PDF / TXT / MD</small>
      </p>
      <p v-else>上传中...</p>
      <input type="file" ref="fileInput" multiple accept=".pdf,.txt,.md,.markdown"
        @change="onSelect" style="display: none" />
    </div>
    <div class="ws-upload-list" v-if="files.length">
      <div class="ws-upload-item" v-for="f in files" :key="f.filename">
        {{ f.filename }} ({{ f.char_count }} 字)
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue'
import { uploadFiles } from '../api.js'
import { useToast } from './Toast.js'

export default {
  name: 'FileUpload',
  props: { scenarioId: Number },
  emits: ['uploaded'],
  setup(props, { emit }) {
    const { show: showToast } = useToast()
    const files = ref([])
    const uploading = ref(false)
    const dragging = ref(false)

    async function handleFiles(fileList) {
      if (!fileList.length || !props.scenarioId) return
      uploading.value = true
      try {
        const result = await uploadFiles(props.scenarioId, Array.from(fileList))
        files.value = result.uploaded || []
        emit('uploaded', result)
      } catch (e) {
        showToast('上传失败: ' + (e.response?.data?.error || e.message))
      } finally {
        uploading.value = false
      }
    }

    function onDrop(e) {
      dragging.value = false
      handleFiles(e.dataTransfer.files)
    }

    function onSelect(e) {
      handleFiles(e.target.files)
    }

    return { files, uploading, dragging, onDrop, onSelect }
  },
}
</script>
