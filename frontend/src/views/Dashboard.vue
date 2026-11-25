<script setup>
import { onMounted, ref } from 'vue'
import { api, auth, brl, STATUS } from '../api'
const d = ref(null), erro = ref('')
onMounted(async () => { try { d.value = await api('/dashboard/') } catch (e) { erro.value = e.message } })
const etapas = ['em_analise', 'aguardando_peca', 'em_servico', 'finalizado']
</script>
<template>
  <div class="topo"><h1>Olá, {{ auth.user?.first_name || auth.user?.username }}</h1><RouterLink class="btn" to="/os/nova">Nova OS</RouterLink></div>
  <div v-if="erro" class="erro">{{ erro }}</div>
  <template v-if="d">
    <div class="grade">
      <div class="num destaque"><b>{{ d.abertas }}</b><span>aparelhos na bancada</span></div>
      <RouterLink v-for="s in etapas" :key="s" :to="{ path: '/os', query: { status: s } }" class="num" style="text-decoration:none;color:inherit">
        <b>{{ d.por_status[s] }}</b><span>{{ STATUS[s] }}</span>
      </RouterLink>
    </div>
    <div v-if="d.saldo_mes !== undefined" class="grade">
      <div class="num"><b>{{ brl(d.entradas_mes) }}</b><span>entradas no mês</span></div>
      <div class="num"><b>{{ brl(d.saidas_mes) }}</b><span>saídas no mês</span></div>
      <div class="num"><b>{{ brl(d.saldo_mes) }}</b><span>saldo do mês</span></div>
      <div class="num"><b>{{ brl(d.a_receber) }}</b><span>a receber (finalizadas)</span></div>
    </div>
    <RouterLink v-if="d.estoque_baixo" to="/estoque" class="card" style="display:block;text-decoration:none;color:var(--alerta)">
      {{ d.estoque_baixo }} peça(s) com estoque baixo. Ver estoque.
    </RouterLink>
  </template>
</template>
