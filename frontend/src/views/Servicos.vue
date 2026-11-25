<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api, auth, brl } from '../api'

const lista = ref([]), busca = ref(''), erro = ref(''), msg = ref(''), editando = ref(null)
const admin = computed(() => auth.user?.cargo === 'admin')
const vazio = () => ({ nome: '', preco: 0, ativo: true })
const f = reactive(vazio())
const carregar = async () => {
  try { lista.value = (await api('/servicos/?search=' + encodeURIComponent(busca.value))).results }
  catch (e) { erro.value = e.message }
}
let t
watch(busca, () => { clearTimeout(t); t = setTimeout(carregar, 300) })
onMounted(carregar)

function editar(s) { editando.value = s.id; Object.assign(f, vazio(), s); window.scrollTo(0, 0) }
function cancelar() { editando.value = null; Object.assign(f, vazio()) }
async function salvar() {
  erro.value = ''; msg.value = ''
  try {
    await api(editando.value ? `/servicos/${editando.value}/` : '/servicos/', {
      method: editando.value ? 'PATCH' : 'POST', body: f,
    })
    msg.value = editando.value ? 'Serviço atualizado.' : 'Serviço criado.'
    cancelar(); carregar()
  } catch (e) { erro.value = e.message }
}
async function alternar(s) {
  erro.value = ''; msg.value = ''
  try {
    await api(`/servicos/${s.id}/`, { method: 'PATCH', body: { ativo: !s.ativo } })
    msg.value = s.ativo ? 'Serviço desativado.' : 'Serviço ativado.'
    carregar()
  } catch (e) { erro.value = e.message }
}
</script>
<template>
  <h1>Serviços</h1>
  <div v-if="erro" class="erro" role="alert">{{ erro }}</div>
  <div v-if="msg" class="card" role="status">{{ msg }}</div>
  <form v-if="admin" class="card" @submit.prevent="salvar">
    <h2>{{ editando ? 'Editar serviço' : 'Novo serviço' }}</h2>
    <div class="linha2">
      <label>Nome<input v-model="f.nome" required /></label>
      <label>Valor (R$)<input v-model="f.preco" type="number" step="0.01" min="0" /></label>
    </div>
    <div class="acoes">
      <button class="btn">Salvar serviço</button>
      <button v-if="editando" type="button" class="btn sec" @click="cancelar">Cancelar</button>
    </div>
  </form>
  <input v-model="busca" type="search" placeholder="Buscar serviço" aria-label="Buscar serviço" style="margin-bottom:.75rem" />
  <ul class="lista">
    <li v-for="s in lista" :key="s.id">
      <div>
        <strong>{{ s.nome }}</strong>
        <span v-if="!s.ativo" class="badge cancelado">inativo</span><br />
        <span class="mudo">{{ brl(s.preco) }}</span>
      </div>
      <div v-if="admin" class="acoes">
        <button class="chip" @click="editar(s)">Editar</button>
        <button class="chip" @click="alternar(s)">{{ s.ativo ? 'Desativar' : 'Ativar' }}</button>
      </div>
    </li>
  </ul>
  <p v-if="!lista.length" class="vazio">Nenhum serviço cadastrado.</p>
</template>
