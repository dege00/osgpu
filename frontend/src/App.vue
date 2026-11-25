<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { auth, logout } from './api'
import LogoSecreta from './components/LogoSecreta.vue'
import PainelTema from './components/PainelTema.vue'
const route = useRoute()
const logado = computed(() => auth.access && !route.meta.publico)
const abas = computed(() => [
  { to: '/', t: 'Início' }, { to: '/os', t: 'Ordens' }, { to: '/clientes', t: 'Clientes' }, { to: '/estoque', t: 'Estoque' }, { to: '/servicos', t: 'Serviços' },
  ...(auth.user?.cargo === 'admin' ? [
    { to: '/financeiro', t: 'Financeiro' }, { to: '/usuarios', t: 'Usuários' }, { to: '/configuracoes', t: 'Ajustes' },
  ] : []),
])
</script>
<template>
  <div v-if="logado" class="shell">
    <aside class="side">
      <div class="marca"><LogoSecreta :tamanho="30" /><span>{{ auth.user?.loja?.nome || 'Assistec' }}</span></div>
      <nav>
        <RouterLink v-for="a in abas" :key="a.to" :to="a.to" class="aba">{{ a.t }}</RouterLink>
      </nav>
      <button class="sair" @click="logout">Sair</button>
    </aside>
    <main class="conteudo"><RouterView /></main>
  </div>
  <RouterView v-else />
  <PainelTema />
</template>
