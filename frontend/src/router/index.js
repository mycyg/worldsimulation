import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'
import Setup from '../views/Setup.vue'
import Entities from '../views/Entities.vue'
import Simulation from '../views/Simulation.vue'
import Report from '../views/Report.vue'

const routes = [
  { path: '/', name: 'home', component: Home },
  { path: '/setup/:id?', name: 'setup', component: Setup, props: true },
  { path: '/entities/:id', name: 'entities', component: Entities, props: true },
  { path: '/simulation/:id', name: 'simulation', component: Simulation, props: true },
  { path: '/report/:id', name: 'report', component: Report, props: true },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
