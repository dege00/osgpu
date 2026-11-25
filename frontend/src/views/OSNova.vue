<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import ChecklistEntrada from '../components/ChecklistEntrada.vue'
const router = useRouter()
const TIPO_KEY = 'assistec.tipo-aparelho'
const tipoSalvo = localStorage.getItem(TIPO_KEY)
const clientes = ref([]), erro = ref(''), salvando = ref(false), novoCliente = ref(false)
const respostas = reactive({}), checklistItens = ref([])
const cli = reactive({ nome: '', telefone: '' })
const f = reactive({
  cliente: '',
  categoria: tipoSalvo === 'celular' ? 'celular' : 'outro',
  tipo_aparelho: '',
  marca: '',
  modelo: '',
  numero_serie: '',
  imei: '',
  senha_aparelho: '',
  acessorios: '',
  defeito: '',
  status: 'em_analise',
  previsao_entrega: null,
  observacao_entrada: '',
})
onMounted(async () => {
  clientes.value = (await api('/clientes/?page_size=200')).results
})
function mudarCategoria() {
  localStorage.setItem(TIPO_KEY, f.categoria)
  if (f.categoria === 'celular') f.tipo_aparelho = ''
  else f.imei = ''
}
async function salvar() {
  erro.value = ''; salvando.value = true
  try {
    if (novoCliente.value) f.cliente = (await api('/clientes/', { method: 'POST', body: cli })).id
    const body = {
      ...f,
      tipo_aparelho: f.categoria === 'celular' ? 'Celular' : f.tipo_aparelho.trim(),
      imei: f.categoria === 'celular' ? f.imei.trim() : '',
      checklist_itens: checklistItens.value,
      observacao_entrada: f.observacao_entrada.trim(),
    }
    const os = await api('/os/', { method: 'POST', body })
    router.push(`/os/${os.id}`)
  } catch (e) { erro.value = e.message } finally { salvando.value = false }
}
</script>
<template>
  <h1>Nova ordem de serviço</h1>
  <form @submit.prevent="salvar">
    <div v-if="erro" class="erro" role="alert">{{ erro }}</div>
    <div class="card">
      <h2>Cliente</h2>
      <template v-if="!novoCliente">
        <label>Selecione<select v-model="f.cliente" required><option value="" disabled>Escolha…</option><option v-for="c in clientes" :key="c.id" :value="c.id">{{ c.nome }} {{ c.telefone && '— ' + c.telefone }}</option></select></label>
        <a href="#" @click.prevent="novoCliente = true">Cadastrar novo cliente</a>
      </template>
      <template v-else>
        <div class="linha2"><label>Nome<input v-model="cli.nome" required /></label><label>WhatsApp<input v-model="cli.telefone" inputmode="tel" required /></label></div>
        <a href="#" @click.prevent="novoCliente = false">Escolher cliente existente</a>
      </template>
    </div>
    <div class="card">
      <h2>Aparelho</h2>
      <div class="linha2">
        <label>Tipo<select v-model="f.categoria" @change="mudarCategoria"><option value="outro">Outro</option><option value="celular">Celular</option></select></label>
        <label>Marca<input v-model="f.marca" /></label>
      </div>
      <div v-if="f.categoria === 'outro'" class="linha2">
        <label>O que é o aparelho?<input v-model="f.tipo_aparelho" placeholder="Placa de vídeo, placa-mãe, processador…" required /></label>
        <label>Modelo<input v-model="f.modelo" /></label>
      </div>
      <div v-else class="linha2">
        <label>Modelo<input v-model="f.modelo" /></label>
        <label>IMEI<input v-model="f.imei" inputmode="numeric" /></label>
      </div>
      <div class="linha2"><label>Nº de série<input v-model="f.numero_serie" /></label><label>Senha / padrão<input v-model="f.senha_aparelho" /></label></div>
      <label>Acessórios deixados<input v-model="f.acessorios" placeholder="Carregador, capa, chip…" /></label>
      <label>Defeito relatado<textarea v-model="f.defeito" required></textarea></label>
      <label>Previsão de entrega<input v-model="f.previsao_entrega" type="date" /></label>
    </div>
    <div class="card">
      <ChecklistEntrada :categoria="f.categoria" :respostas="respostas" @update:checklist-itens="checklistItens = $event" />
    </div>
    <div class="card">
      <h2>Observações (opcional)</h2>
      <p class="mudo">Opcional. Escreva só o que não coube no checklist.</p>
      <label>Observações<textarea v-model="f.observacao_entrada" rows="4" maxlength="2000"></textarea></label>
    </div>
    <div class="acoes">
      <button class="btn" :disabled="salvando">Abrir OS</button>
      <button type="button" class="btn sec" @click="f.status = f.status === 'orcamento' ? 'em_analise' : 'orcamento'">{{ f.status === 'orcamento' ? 'Será um orçamento ✓' : 'Apenas orçamento' }}</button>
    </div>
  </form>
</template>
