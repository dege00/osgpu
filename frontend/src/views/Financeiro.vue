<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { api, brl, dataBR } from '../api'
const hoje = new Date(), ini = new Date(hoje.getFullYear(), hoje.getMonth(), 1)
const iso = (d) => d.toLocaleDateString('sv-SE')
const de = ref(iso(ini)), ate = ref(iso(hoje)), lista = ref([]), resumo = ref({}), erro = ref('')
const f = reactive({ tipo: 'saida', descricao: '', valor: '', forma: 'dinheiro' })
async function carregar() {
  try {
    const q = `de=${de.value}&ate=${ate.value}`
    lista.value = (await api(`/lancamentos/?${q}&page_size=200`)).results
    resumo.value = await api(`/lancamentos/resumo/?${q}`)
  } catch (e) { erro.value = e.message }
}
onMounted(carregar); watch([de, ate], carregar)
async function salvar() { erro.value = ''; try { await api('/lancamentos/', { method: 'POST', body: f }); f.descricao = ''; f.valor = ''; carregar() } catch (e) { erro.value = e.message } }
async function remover(id) {
  if (!confirm('Excluir lançamento?')) return
  erro.value = ''
  try { await api(`/lancamentos/${id}/`, { method: 'DELETE' }); carregar() }
  catch (e) { erro.value = e.message }
}
</script>
<template>
  <h1>Financeiro</h1>
  <div class="linha2"><label>De<input type="date" v-model="de" /></label><label>Até<input type="date" v-model="ate" /></label></div>
  <div class="grade">
    <div class="num"><b>{{ brl(resumo.entradas) }}</b><span>entradas</span></div>
    <div class="num"><b>{{ brl(resumo.saidas) }}</b><span>saídas</span></div>
    <div class="num destaque"><b>{{ brl(resumo.saldo) }}</b><span>saldo</span></div>
  </div>
  <form class="card" @submit.prevent="salvar">
    <h2>Novo lançamento</h2><div v-if="erro" class="erro">{{ erro }}</div>
    <div class="linha2"><label>Tipo<select v-model="f.tipo"><option value="saida">Saída (despesa)</option><option value="entrada">Entrada</option></select></label>
      <label>Valor (R$)<input v-model="f.valor" type="number" step="0.01" min="0.01" required /></label></div>
    <label>Descrição<input v-model="f.descricao" required placeholder="Ex.: compra de telas, aluguel, venda de capinha" /></label>
    <button class="btn">Lançar</button>
  </form>
  <ul class="lista"><li v-for="l in lista" :key="l.id">
    <div><strong>{{ l.descricao }}</strong><br /><span class="mudo">{{ dataBR(l.data + 'T12:00') }} · {{ l.forma }}</span></div>
    <div style="text-align:right"><strong :style="{ color: l.tipo === 'entrada' ? 'var(--verde)' : 'var(--alerta)' }">{{ l.tipo === 'saida' ? '−' : '+' }} {{ brl(l.valor) }}</strong><br /><button class="chip" @click="remover(l.id)">Excluir</button></div></li></ul>
  <p v-if="!lista.length" class="vazio">Sem lançamentos no período.</p>
</template>
