<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { api, auth, brl } from '../api'
const lista = ref([]), busca = ref(''), erro = ref(''), editando = ref(null), lendo = ref(false)
const admin = computed(() => auth.user?.cargo === 'admin')
const vazio = () => ({ nome: '', sku: '', custo: 0, preco: 0, quantidade: 0, minimo: 1 })
const f = reactive(vazio())
const carregar = async () => { try { lista.value = (await api('/pecas/?search=' + encodeURIComponent(busca.value))).results } catch (e) { erro.value = e.message } }
let t; watch(busca, () => { clearTimeout(t); t = setTimeout(carregar, 300) }); onMounted(carregar)
function editar(p) { editando.value = p.id; Object.assign(f, vazio(), p); window.scrollTo(0, 0) }
function cancelar() { editando.value = null; Object.assign(f, vazio()) }
async function salvar() {
  erro.value = ''
  try { await api(editando.value ? `/pecas/${editando.value}/` : '/pecas/', { method: editando.value ? 'PATCH' : 'POST', body: f }); cancelar(); carregar() }
  catch (e) { erro.value = e.message }
}
// Leitura de código de barras pela câmera (BarcodeDetector: Chrome/Android). Sem suporte, digite o código.
const suportaCamera = 'BarcodeDetector' in window
async function lerCodigo() {
  lendo.value = true
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
    const v = document.createElement('video'); v.srcObject = stream; await v.play()
    const det = new BarcodeDetector()
    const fim = Date.now() + 15000
    while (Date.now() < fim) {
      const r = await det.detect(v); if (r.length) { f.sku = r[0].rawValue; break }
      await new Promise(r => setTimeout(r, 300))
    }
    stream.getTracks().forEach(t => t.stop())
  } catch (e) { erro.value = 'Não foi possível abrir a câmera: ' + e.message } finally { lendo.value = false }
}
</script>
<template>
  <h1>Estoque de peças</h1>
  <form class="card" @submit.prevent="salvar">
    <h2>{{ editando ? 'Editar peça' : 'Nova peça' }}</h2>
    <div v-if="erro" class="erro">{{ erro }}</div>
    <div class="linha2"><label>Nome<input v-model="f.nome" required /></label>
      <label>Código / código de barras<input v-model="f.sku" /></label></div>
    <button v-if="suportaCamera" type="button" class="btn sec" style="margin-bottom:.75rem" :disabled="lendo" @click="lerCodigo">{{ lendo ? 'Lendo… aponte a câmera' : 'Ler código com a câmera' }}</button>
    <div class="linha2">
      <label v-if="admin">Custo (R$)<input v-model="f.custo" type="number" step="0.01" min="0" /></label>
      <label>Preço de venda (R$)<input v-model="f.preco" type="number" step="0.01" min="0" /></label>
    </div>
    <div class="linha2"><label>Quantidade<input v-model.number="f.quantidade" type="number" /></label><label>Estoque mínimo<input v-model.number="f.minimo" type="number" min="0" /></label></div>
    <div class="acoes"><button class="btn">Salvar peça</button><button v-if="editando" type="button" class="btn sec" @click="cancelar">Cancelar</button></div>
  </form>
  <input v-model="busca" type="search" placeholder="Buscar peça ou código" aria-label="Buscar peça" style="margin-bottom:.75rem" />
  <ul class="lista"><li v-for="p in lista" :key="p.id">
    <div><strong>{{ p.nome }}</strong> <span v-if="p.estoque_baixo" class="badge aguardando_peca">estoque baixo</span><br /><span class="mudo">{{ p.quantidade }} un · <template v-if="admin">custo {{ brl(p.custo) }} · </template>venda {{ brl(p.preco) }}</span></div>
    <button class="chip" @click="editar(p)">Editar</button></li></ul>
  <p v-if="!lista.length" class="vazio">Nenhuma peça cadastrada.</p>
</template>
