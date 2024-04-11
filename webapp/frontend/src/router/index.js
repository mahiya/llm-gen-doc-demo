import { createRouter, createWebHistory } from 'vue-router'
import ReferenceView from '../views/ReferenceView.vue'
import SourceView from '../views/SourceView.vue'
import GenerateView from '../views/GenerateView.vue'

const routes = [
  {
    path: '/',
    name: 'reference',
    component: ReferenceView
  },
  {
    path: '/source',
    name: 'source',
    component: SourceView
  },
  {
    path: '/generate',
    name: 'generate',
    component: GenerateView
  }
]

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

export default router
