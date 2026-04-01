<template>
  <div class="ws-drawer-overlay" @click.self="$emit('close')">
    <div class="ws-drawer">
      <div class="ws-drawer-header">
        <h3>编辑角色卡: {{ entity.name }}</h3>
        <button class="ws-btn-sm" @click="$emit('close')">✕</button>
      </div>

      <div class="ws-drawer-body">
        <div class="ws-form-group">
          <label>名称</label>
          <input v-model="form.name" />
        </div>
        <div class="ws-form-group">
          <label>类型</label>
          <select v-model="form.type">
            <option value="Person">Person</option>
            <option value="Organization">Organization</option>
            <option value="Institution">Institution</option>
            <option value="Force">Force</option>
          </select>
        </div>
        <div class="ws-form-group">
          <label>阵营</label>
          <input v-model="form.faction" />
        </div>
        <div class="ws-form-group">
          <label>描述</label>
          <textarea v-model="form.description" rows="3"></textarea>
        </div>
        <div class="ws-form-group">
          <label>性格/立场</label>
          <textarea v-model="form.personality" rows="2"></textarea>
        </div>
        <div class="ws-form-group">
          <label>动机</label>
          <input v-model="form.motivation" />
        </div>
        <div class="ws-form-group">
          <label>人设 (Persona)</label>
          <textarea v-model="form.persona" rows="4" placeholder="详细的角色背景和人设描述..."></textarea>
        </div>
        <div class="ws-form-group">
          <label>外貌描述</label>
          <textarea v-model="form.appearance" rows="2"></textarea>
        </div>
        <div class="ws-form-group">
          <label>说话风格</label>
          <input v-model="form.speech_style" placeholder="如：正式/口语化/学术..." />
        </div>
        <div class="ws-form-group">
          <label>初始状态</label>
          <textarea v-model="form.initial_status" rows="2"></textarea>
        </div>
        <div class="ws-form-group">
          <label>重要度 (1-10)</label>
          <input v-model.number="form.prominence" type="number" min="1" max="10" />
        </div>
        <div class="ws-form-group">
          <label>标签</label>
          <input v-model="form.tags" placeholder="逗号分隔" />
        </div>
      </div>

      <div class="ws-drawer-footer">
        <button class="ws-btn primary" @click="$emit('save', form)">保存</button>
        <button class="ws-btn" @click="$emit('close')">取消</button>
      </div>
    </div>
  </div>
</template>

<script>
import { reactive } from 'vue'

export default {
  name: 'EntityEditor',
  props: { entity: Object },
  emits: ['save', 'close'],
  setup(props) {
    const form = reactive({ ...props.entity })
    return { form }
  },
}
</script>
