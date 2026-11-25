<script setup>
import { onMounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { api, STATUS } from '../api'
const route = useRoute()
const itens = ref([]), busca = ref(''), status = ref(route.query.status || ''), erro = ref('')
async function carregar() {
  try {
    const q = new URLSearchParams()
    if (busca.value) q.set('search', busca.value)
    if (status.value) q.set('status', status.value)
    itens.value = (await api('/os/?' + q)).results
  } catch (e) { erro.value = e.message }
}
let t; watch(busca, () => { clearTimeout(t); t = setTimeout(carregar, 300) })
watch(status, carregar); onMounted(carregar)
</script>
<template>
  <div class="topo"><h1>Ordens de serviço</h1><RouterLink class="btn" to="/os/nova">Nova OS</RouterLink></div>
  <input v-model="busca" type="search" placeholder="Buscar por nº, cliente, modelo, nº de série ou IMEI" aria-label="Buscar OS" />
  <div class="filtros" style="margin-top:.6rem">
    <button class="chip" :class="{ on: !status }" @click="status = ''">Todas</button>
    <button v-for="(l, k) in STATUS" :key="k" class="chip" :class="{ on: status === k }" @click="status = k">{{ l }}</button>
  </div>
  <div v-if="erro" class="erro">{{ erro }}</div>
  <ul class="lista">
    <li v-for="o in itens" :key="o.id">
      <RouterLink class="item" :to="`/os/${o.id}`">
        <strong>#{{ o.numero }} · {{ o.cliente_nome }}</strong><br />
        <span class="mudo">{{ o.tipo_aparelho }} {{ o.marca }} {{ o.modelo }} — {{ o.defeito.slice(0, 60) }}</span>
      </RouterLink>
      <span class="badge" :class="o.status">{{ o.status_label }}</span>
    </li>
  </ul>
  <p v-if="!itens.length" class="vazio">Nenhuma OS encontrada.</p>
</template>
