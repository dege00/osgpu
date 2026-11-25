<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api'

const props = defineProps({ categoria: { type: String, required: true } })
const emit = defineEmits(['fechar', 'renomeado', 'removido'])
const itens = ref([]), novo = ref(''), erro = ref(''), salvando = ref(false)

async function carregar() {
  erro.value = ''
  try {
    const dados = await api(`/checklist-itens/?categoria=${encodeURIComponent(props.categoria)}`)
    itens.value = (Array.isArray(dados) ? dados : dados.results || []).map(i => ({ ...i, original: i.nome }))
  } catch (e) { erro.value = e.message }
}
onMounted(carregar)

async function salvarNome(item) {
  const nome = item.nome.trim()
  if (!nome || nome === item.original) { item.nome = item.original; return }
  const antigo = item.original
  erro.value = ''; salvando.value = true
  try {
    const atual = await api(`/checklist-itens/${item.id}/`, { method: 'PATCH', body: { nome } })
    item.nome = atual.nome; item.original = atual.nome
    emit('renomeado', { antigo, novo: atual.nome })
  } catch (e) {
    erro.value = e.message
    item.nome = item.original
    await carregar()
  } finally { salvando.value = false }
}

async function mover(item, delta) {
  const atual = itens.value.findIndex(i => i.id === item.id)
  const destino = atual + delta
  if (atual < 0 || destino < 0 || destino >= itens.value.length) return
  const novaOrdem = [...itens.value]
  const tmp = novaOrdem[atual]
  novaOrdem[atual] = novaOrdem[destino]
  novaOrdem[destino] = tmp
  erro.value = ''; salvando.value = true
  try {
    await api('/checklist-itens/reordenar/', {
      method: 'POST', body: { categoria: props.categoria, ids: novaOrdem.map(i => i.id) },
    })
    itens.value = novaOrdem.map((i, idx) => ({ ...i, ordem: idx + 1, original: i.nome }))
  } catch (e) {
    erro.value = e.message
    await carregar()
  } finally { salvando.value = false }
}

async function remover(item) {
  if (!confirm(`Remover o item "${item.nome}"?`)) return
  erro.value = ''; salvando.value = true
  try {
    await api(`/checklist-itens/${item.id}/`, { method: 'DELETE' })
    itens.value = itens.value.filter(i => i.id !== item.id)
    emit('removido', item.nome)
  } catch (e) { erro.value = e.message } finally { salvando.value = false }
}

async function adicionar() {
  const nome = novo.value.trim()
  if (!nome) return
  erro.value = ''; salvando.value = true
  try {
    const criado = await api('/checklist-itens/', { method: 'POST', body: { categoria: props.categoria, nome } })
    itens.value.push({ ...criado, original: criado.nome })
    novo.value = ''
  } catch (e) { erro.value = e.message } finally { salvando.value = false }
}
</script>
<template>
  <div class="editor-checklist">
    <p class="mudo">Edite os itens desta categoria. As mudanças valem para novas OS; as antigas não são alteradas.</p>
    <div v-if="erro" class="erro" role="alert">{{ erro }}</div>
    <div v-for="(item, i) in itens" :key="item.id" class="editor-item">
      <input v-model="item.nome" :aria-label="`Nome do item ${i + 1}`" maxlength="80" @blur="salvarNome(item)" @keydown.enter.prevent="$event.target.blur()" />
      <button type="button" class="chip" :disabled="i === 0 || salvando" :aria-label="`Subir ${item.nome}`" @click="mover(item, -1)">↑</button>
      <button type="button" class="chip" :disabled="i === itens.length - 1 || salvando" :aria-label="`Descer ${item.nome}`" @click="mover(item, 1)">↓</button>
      <button type="button" class="chip" :disabled="salvando" @click="remover(item)">Remover</button>
    </div>
    <div class="editor-item">
      <input v-model="novo" placeholder="Novo item" aria-label="Nome do novo item" maxlength="80" />
      <button type="button" class="btn" :disabled="salvando" @click="adicionar">Adicionar item</button>
    </div>
    <button type="button" class="chip" @click="emit('fechar')">Fechar edição</button>
  </div>
</template>
<style scoped>
.editor-checklist { margin: .75rem 0; padding: .75rem; border: 1px solid var(--linha); border-radius: 8px }
.editor-item { display: flex; gap: .5rem; align-items: center; flex-wrap: wrap; margin: .4rem 0 }
.editor-item input { flex: 1 1 12rem; min-height: 44px }
.editor-item .chip, .editor-item .btn { min-height: 44px }
</style>
