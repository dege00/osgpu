<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { api, auth } from '../api'
import ChecklistEditor from './ChecklistEditor.vue'

const props = defineProps({
  categoria: { type: String, required: true },
  respostas: { type: Object, required: true },
})
const emit = defineEmits(['update:checklistItens'])
const itens = ref([]), erro = ref(''), carregando = ref(false), editor = ref(false)
const admin = computed(() => auth.user?.cargo === 'admin')

function emitir() {
  emit('update:checklistItens', itens.value
    .filter(i => props.respostas[i.nome])
    .map(i => ({ nome: i.nome, resposta: props.respostas[i.nome] })))
}

async function carregar(manterRespostas) {
  carregando.value = true; erro.value = ''
  if (!manterRespostas) for (const nome of Object.keys(props.respostas)) delete props.respostas[nome]
  try {
    const dados = await api(`/checklist-itens/?categoria=${encodeURIComponent(props.categoria)}`)
    itens.value = Array.isArray(dados) ? dados : dados.results || []
    if (!itens.value.length) erro.value = 'Nenhum item cadastrado para esta categoria. Você ainda pode abrir a OS.'
  } catch (e) {
    itens.value = []
    erro.value = 'Não foi possível carregar o checklist. Você ainda pode abrir a OS.'
  } finally { carregando.value = false; emitir() }
}

function marcar(nome, resposta) {
  props.respostas[nome] = props.respostas[nome] === resposta ? '' : resposta
  emitir()
}

function aoRenomear({ antigo, novo }) {
  if (antigo in props.respostas) {
    props.respostas[novo] = props.respostas[antigo]
    delete props.respostas[antigo]
  }
  emitir()
}

function aoRemover(nome) { delete props.respostas[nome]; emitir() }

async function aoFechar() {
  editor.value = false
  await carregar(true)
  const nomes = new Set(itens.value.map(i => i.nome))
  for (const nome of Object.keys(props.respostas)) if (!nomes.has(nome)) delete props.respostas[nome]
  emitir()
}

onMounted(() => carregar(false))
watch(() => props.categoria, () => carregar(false))
</script>
<template>
  <div class="checklist-entrada">
    <div class="titulo-checklist">
      <h2>Checklist de entrada</h2>
      <button v-if="admin" type="button" class="chip" aria-label="Editar itens do checklist" @click="editor = true">⚙️ Editar</button>
    </div>
    <p class="mudo">Registre o estado do aparelho ao receber. Fica registrado como prova.</p>
    <div v-if="erro" class="erro" role="alert">{{ erro }}</div>
    <ChecklistEditor v-if="editor" :categoria="categoria" @fechar="aoFechar" @renomeado="aoRenomear" @removido="aoRemover" />
    <p v-if="carregando" class="mudo">Carregando checklist…</p>
    <div v-for="item in itens" :key="item.id" class="linha-checklist">
      <span class="nome-item">{{ item.nome }}</span>
      <div class="opcoes" :aria-label="`Resposta para ${item.nome}`">
        <button type="button" class="chip resposta" :class="{ on: respostas[item.nome] === 'sim' }" :aria-pressed="respostas[item.nome] === 'sim'" @click="marcar(item.nome, 'sim')">Sim</button>
        <button type="button" class="chip resposta" :class="{ on: respostas[item.nome] === 'nao' }" :aria-pressed="respostas[item.nome] === 'nao'" @click="marcar(item.nome, 'nao')">Não</button>
      </div>
    </div>
  </div>
</template>
<style scoped>
.titulo-checklist { display: flex; align-items: center; gap: .75rem }
.titulo-checklist h2 { margin: 0 }
.linha-checklist { display: flex; justify-content: space-between; align-items: center; gap: .75rem; flex-wrap: wrap; padding: .5rem 0; border-bottom: 1px solid var(--linha) }
.nome-item { min-width: 10rem; flex: 1 1 10rem }
.opcoes { display: flex; gap: .5rem }
.opcoes .resposta { min-width: 64px; min-height: 44px }
</style>
