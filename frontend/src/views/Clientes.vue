<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { api } from '../api'
const lista = ref([]), busca = ref(''), erro = ref(''), editando = ref(null)
const vazio = () => ({ nome: '', telefone: '', email: '', documento: '', observacoes: '' })
const f = reactive(vazio())
const carregar = async () => { try { lista.value = (await api('/clientes/?search=' + encodeURIComponent(busca.value))).results } catch (e) { erro.value = e.message } }
let t; watch(busca, () => { clearTimeout(t); t = setTimeout(carregar, 300) }); onMounted(carregar)
function editar(c) { editando.value = c.id; Object.assign(f, c); window.scrollTo(0, 0) }
function cancelar() { editando.value = null; Object.assign(f, vazio()) }
async function salvar() {
  erro.value = ''
  try {
    await api(editando.value ? `/clientes/${editando.value}/` : '/clientes/', { method: editando.value ? 'PUT' : 'POST', body: f })
    cancelar(); carregar()
  } catch (e) { erro.value = e.message }
}
</script>
<template>
  <h1>Clientes</h1>
  <form class="card" @submit.prevent="salvar">
    <h2>{{ editando ? 'Editar cliente' : 'Novo cliente' }}</h2>
    <div v-if="erro" class="erro">{{ erro }}</div>
    <div class="linha2"><label>Nome<input v-model="f.nome" required /></label><label>WhatsApp<input v-model="f.telefone" inputmode="tel" /></label></div>
    <div class="linha2"><label>CPF/CNPJ<input v-model="f.documento" /></label><label>E-mail<input v-model="f.email" type="email" /></label></div>
    <div class="acoes"><button class="btn">Salvar cliente</button><button v-if="editando" type="button" class="btn sec" @click="cancelar">Cancelar</button></div>
  </form>
  <input v-model="busca" type="search" placeholder="Buscar cliente" aria-label="Buscar cliente" style="margin-bottom:.75rem" />
  <ul class="lista"><li v-for="c in lista" :key="c.id"><div><strong>{{ c.nome }}</strong><br /><span class="mudo">{{ c.telefone }}</span></div><button class="chip" @click="editar(c)">Editar</button></li></ul>
  <p v-if="!lista.length" class="vazio">Nenhum cliente ainda. Cadastre o primeiro acima.</p>
</template>
