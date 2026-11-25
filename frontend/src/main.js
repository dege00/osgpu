import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'
import { auth } from './api'
import './style.css'
import { iniciarTema } from './composables/useTema'

const routes = [
  { path: '/login', component: () => import('./views/Login.vue'), meta: { publico: true } },
  { path: '/r/:token', component: () => import('./views/Acompanhar.vue'), meta: { publico: true } },
  { path: '/', component: () => import('./views/Dashboard.vue') },
  { path: '/os', component: () => import('./views/OSList.vue') },
  { path: '/os/nova', component: () => import('./views/OSNova.vue') },
  { path: '/os/:id', component: () => import('./views/OSDetalhe.vue') },
  { path: '/os/:id/imprimir', component: () => import('./views/OSImprimir.vue') },
  { path: '/clientes', component: () => import('./views/Clientes.vue') },
  { path: '/estoque', component: () => import('./views/Estoque.vue') },
  { path: '/servicos', component: () => import('./views/Servicos.vue') },
  { path: '/financeiro', component: () => import('./views/Financeiro.vue'), meta: { admin: true } },
  { path: '/usuarios', component: () => import('./views/Usuarios.vue'), meta: { admin: true } },
  { path: '/configuracoes', component: () => import('./views/Configuracoes.vue'), meta: { admin: true } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]
const router = createRouter({ history: createWebHistory(), routes })
router.beforeEach((to) => {
  if (to.meta.publico) return true
  if (!auth.access) return '/login'
  if (to.meta.admin && auth.user?.cargo !== 'admin') return '/'
})
iniciarTema()   // aplica o tema salvo (cache) já na primeira pintura e atualiza pelo servidor
createApp(App).use(router).mount('#app')
