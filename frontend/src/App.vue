<template>
  <div id="ws-app">
    <header class="ws-header">
      <h1 @click="$router.push('/')" class="ws-logo">WorldSim</h1>
      <nav class="ws-nav" v-if="currentScenario">
        <router-link :to="`/setup/${currentScenario}`">场景设置</router-link>
        <router-link :to="`/entities/${currentScenario}`">实体管理</router-link>
        <router-link :to="`/simulation/${currentScenario}`">推演</router-link>
        <router-link :to="`/report/${currentScenario}`">报告</router-link>
      </nav>
    </header>
    <main class="ws-main">
      <router-view />
    </main>
    <ToastContainer />
  </div>
</template>

<script>
import ToastContainer from './components/ToastContainer.vue'
export default {
  name: 'App',
  components: { ToastContainer },
  computed: {
    currentScenario() {
      const id = this.$route.params.id
      return id || null
    },
  },
}
</script>
