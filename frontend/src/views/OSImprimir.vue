<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { api, auth, brl, dataHoraBR, setSession } from '../api'
import { urlMidia } from '../utils/midia'

const route = useRoute()
const os = ref(null), erro = ref(''), papel = ref('80')
const loja = computed(() => auth.user?.loja || {})
const restante = computed(() => os.value ? Number(os.value.total) - Number(os.value.pago) : 0)
const checklistItens = computed(() => Array.isArray(os.value?.checklist_itens) ? os.value.checklist_itens : [])
const linkPublico = computed(() => os.value ? `${location.origin}/r/${os.value.token}` : '')
function imprimir() { window.print() }

onMounted(async () => {
  try {
    const [ordem, usuario] = await Promise.all([api(`/os/${route.params.id}/`), api('/auth/eu/')])
    os.value = ordem
    setSession({ usuario })
  } catch (e) { erro.value = e.message }
})
</script>

<template>
  <div class="topo no-print">
    <h1>Imprimir OS</h1>
    <div class="acoes">
      <button class="chip" :class="{ on: papel === '58' }" @click="papel = '58'">58 mm</button>
      <button class="chip" :class="{ on: papel === '80' }" @click="papel = '80'">80 mm</button>
      <button class="btn" @click="imprimir">Imprimir</button>
      <RouterLink class="btn sec" :to="`/os/${route.params.id}`">Voltar</RouterLink>
    </div>
  </div>
  <div v-if="erro" class="erro">{{ erro }}</div>

  <div v-if="os" class="recibo" :class="{ r58: papel === '58' }">
    <header>
      <img v-if="loja.logo" :src="urlMidia(loja.logo)" alt="" class="logo" />
      <h1>{{ loja.nome }}</h1>
      <p v-if="loja.documento">CNPJ/CPF: {{ loja.documento }}</p>
      <p v-if="loja.telefone">Tel./WhatsApp: {{ loja.telefone }}</p>
      <p v-if="loja.endereco">{{ loja.endereco }}</p>
    </header>
    <hr />
    <p class="centro-txt"><strong>{{ os.status_label === 'Orçamento' ? 'ORÇAMENTO' : 'ORDEM DE SERVIÇO' }} Nº {{ os.numero }}</strong><br />
      {{ dataHoraBR(os.criado_em) }}</p>
    <hr />
    <p><strong>Cliente:</strong> {{ os.cliente_nome }}</p>
    <p v-if="os.cliente_telefone"><strong>Telefone:</strong> {{ os.cliente_telefone }}</p>
    <p><strong>Aparelho:</strong> {{ os.tipo_aparelho }} {{ os.marca }} {{ os.modelo }}</p>
    <p v-if="os.numero_serie"><strong>Nº de série:</strong> {{ os.numero_serie }}</p>
    <p v-if="os.imei"><strong>IMEI:</strong> {{ os.imei }}</p>
    <p><strong>Defeito:</strong> {{ os.defeito }}</p>
    <p v-if="os.laudo"><strong>Laudo:</strong> {{ os.laudo }}</p>
    <template v-if="checklistItens.length || os.checklist || os.observacao_entrada">
      <template v-if="checklistItens.length">
        <p><strong>Checklist de entrada:</strong></p>
        <p v-for="(i, idx) in checklistItens" :key="idx" class="checklist">{{ i.nome }}: {{ i.resposta === 'sim' ? 'Sim' : 'Não' }}</p>
      </template>
      <template v-if="os.checklist">
        <p><strong>Checklist anterior:</strong></p>
        <p class="checklist">{{ os.checklist }}</p>
      </template>
      <p v-if="os.observacao_entrada"><strong>Observações:</strong> {{ os.observacao_entrada }}</p>
    </template>
    <hr />
    <table>
      <thead><tr><th>Item</th><th class="r">Qtd</th><th class="r">Unit.</th><th class="r">Total</th></tr></thead>
      <tbody>
        <tr v-for="i in os.itens" :key="i.id">
          <td>{{ i.descricao }}</td><td class="r">{{ i.quantidade }}</td>
          <td class="r">{{ brl(i.valor_unitario) }}</td><td class="r">{{ brl(i.subtotal) }}</td>
        </tr>
      </tbody>
    </table>
    <hr />
    <p class="linha"><span>Subtotal</span><span>{{ brl(os.subtotal) }}</span></p>
    <p v-if="Number(os.desconto)" class="linha"><span>Desconto</span><span>- {{ brl(os.desconto) }}</span></p>
    <p class="linha total"><span>TOTAL</span><span>{{ brl(os.total) }}</span></p>
    <p class="linha"><span>Pago</span><span>{{ brl(os.pago) }}</span></p>
    <p v-if="restante > 0" class="linha"><span>Restante</span><span>{{ brl(restante) }}</span></p>
    <hr />
    <p class="pequeno"><strong>Garantia:</strong> {{ os.garantia_dias }} dias. {{ loja.termo_garantia }}</p>
    <p v-if="os.assinatura" class="assinatura"><img :src="urlMidia(os.assinatura)" alt="Assinatura do cliente" /></p>
    <p class="centro-txt pequeno">Obrigado pela confiança! Acompanhe em {{ linkPublico }}</p>
  </div>
</template>

<style scoped>
.recibo { width: 80mm; max-width: 100%; margin: 0 auto; background: #fff; color: #000; padding: 3mm; border: 1px solid var(--linha); border-radius: 6px; font-size: 11px; line-height: 1.35 }
.recibo.r58 { width: 58mm; font-size: 10px }
.recibo header { text-align: center }
.recibo .logo { max-width: 40mm; max-height: 18mm; object-fit: contain; margin-bottom: 1mm }
.recibo h1 { font-size: 13px; margin: 0 }
.recibo p { margin: 1mm 0 }
.recibo hr { border: 0; border-top: 1px dashed #000; margin: 2mm 0 }
.recibo table { width: 100%; border-collapse: collapse; font-size: inherit }
.recibo th, .recibo td { padding: .5mm 0; border-bottom: 1px dotted #999; text-align: left }
.recibo .r { text-align: right }
.recibo .linha { display: flex; justify-content: space-between; gap: 1rem }
.recibo .total { font-weight: 700; font-size: 1.1em }
.recibo .centro-txt { text-align: center }
.recibo .pequeno { font-size: .9em }
.recibo .checklist { white-space: pre-line }
.recibo .assinatura { text-align: center; margin-top: 3mm }
.recibo .assinatura img { max-width: 100%; max-height: 22mm }
@media print {
  .recibo { border: 0; border-radius: 0; width: 80mm; padding: 0; margin: 0 }
  .recibo.r58 { width: 58mm }
  @page { margin: 3mm; }
}
</style>
