<template>
  <div class="ws-faction-list">
    <div class="ws-faction-block" v-for="(entities, faction) in factions" :key="faction">
      <div class="ws-faction-header" @click="toggle(faction)">
        {{ faction }} ({{ entities.length }})
        <span class="ws-toggle">{{ expanded[faction] ? '▲' : '▼' }}</span>
      </div>
      <div class="ws-faction-members" v-show="expanded[faction]">
        <div class="ws-entity-card" v-for="e in entities" :key="e.id" @click="$emit('edit', e)">
          <div class="ws-entity-card-header">
            <strong>{{ e.name }}</strong>
            <span class="ws-tag" :class="e.status || 'active'">{{ e.status || 'active' }}</span>
          </div>
          <div class="ws-entity-card-body">
            <small>{{ e.type }} | P:{{ e.prominence }}</small>
            <p>{{ (e.description || '').substring(0, 50) }}</p>
          </div>
          <div class="ws-entity-card-actions">
            <button class="ws-btn-sm" @click.stop="$emit('edit', e)">编辑</button>
            <button class="ws-btn-sm danger" @click.stop="$emit('delete', e)">删除</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref, reactive } from 'vue'

export default {
  name: 'FactionList',
  props: { factions: Object },
  emits: ['edit', 'delete'],
  setup() {
    const expanded = reactive({})
    function toggle(faction) {
      expanded[faction] = !expanded[faction]
    }
    return { expanded, toggle }
  },
}
</script>
