<template>
  <Teleport to="body">
    <div class="ws-toast-container" v-if="toasts.length">
      <div class="ws-toast" v-for="t in toasts" :key="t.id" :class="t.type">
        {{ t.message }}
      </div>
    </div>
  </Teleport>
</template>

<script>
import { useToast } from './Toast.js'
export default {
  name: 'ToastContainer',
  setup() {
    const { toasts } = useToast()
    return { toasts }
  },
}
</script>

<style scoped>
.ws-toast-container {
  position: fixed;
  top: 16px;
  right: 16px;
  z-index: 1000;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ws-toast {
  padding: 10px 16px;
  border-radius: 6px;
  font-size: 13px;
  max-width: 400px;
  animation: toast-in 0.2s ease;
}
.ws-toast.error { background: #c0392b; color: #fff; }
.ws-toast.warn { background: #e67e22; color: #fff; }
.ws-toast.info { background: #2980b9; color: #fff; }
@keyframes toast-in { from { opacity: 0; transform: translateY(-8px); } to { opacity: 1; transform: translateY(0); } }
</style>
