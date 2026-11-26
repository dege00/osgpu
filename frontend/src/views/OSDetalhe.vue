<script setup>
import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import Assinatura from '../components/Assinatura.vue'
import { api, auth, brl, dataBR, dataHoraBR, STATUS } from '../api'
import { comprimirImagem } from '../utils/imagem'
import { urlMidia } from '../utils/midia'
const route = useRoute(), router = useRouter()
const os = ref(null), pecas = ref([]), erro = ref(''), msg = ref('')
const inputCamera = ref(null), inputGaleria = ref(null), inputLaudo = ref(null)
const enviandoFoto = ref(false), fotoAtual = ref(0), fotoTotal = ref(0), fotoSalvando = ref(null)
const gerandoLaudo = ref(false)
const LIMITE_FOTO_ORIGINAL = 20 * 1024 * 1024
const item = reactive({ tipo: 'servico', peca: '', descricao: '', quantidade: 1, valor_unitario: '' })
const forma = ref('pix'), valorPagamento = ref('')
const itemEdit = reactive({ id: null, quantidade: 1, valor_unitario: '' })
const admin = computed(() => auth.user?.cargo === 'admin')
const restante = computed(() => os.value ? Number(os.value.total) - Number(os.value.pago) : 0)
const wrap = (fn) => async (...a) => { erro.value = ''; msg.value = ''; try { await fn(...a) } catch (e) { erro.value = e.message } }

const carregar = wrap(async () => { os.value = await api(`/os/${route.params.id}/`) })
async function recarregarFotos() {
  if (!os.value) return
  try {
    const atual = await api(`/os/${route.params.id}/`)
    os.value.fotos = atual.fotos
  } catch { /* mantém a tela atual se a atualização falhar */ }
}
function aoVoltar() {
  if (document.visibilityState === 'visible' && os.value) recarregarFotos()
}
onMounted(async () => {
  document.addEventListener('visibilitychange', aoVoltar)
  window.addEventListener('pageshow', aoVoltar)
  await carregar()
  pecas.value = (await api('/pecas/?page_size=200')).results
})
onUnmounted(() => {
  document.removeEventListener('visibilitychange', aoVoltar)
  window.removeEventListener('pageshow', aoVoltar)
})

const mudarStatus = wrap(async (s) => { os.value = await api(`/os/${os.value.id}/status/`, { method: 'POST', body: { status: s } }) })
const salvarLaudo = wrap(async () => { await api(`/os/${os.value.id}/`, { method: 'PATCH', body: { laudo: os.value.laudo, desconto: os.value.desconto } }); await carregar(); msg.value = 'Salvo.' })
const gerarLaudo = wrap(async () => {
  gerandoLaudo.value = true
  try {
    const { texto } = await api(`/os/${os.value.id}/laudo-sugerido/`)
    if ((os.value.laudo || '').trim() && !confirm('Substituir o laudo atual pelo laudo gerado automaticamente?')) return
    os.value.laudo = texto
    msg.value = 'Laudo gerado. Revise, complemente e clique em Salvar.'
    await nextTick()
    const area = inputLaudo.value
    if (area) {
      area.focus()
      area.setSelectionRange(area.value.length, area.value.length)
    }
  } finally {
    gerandoLaudo.value = false
  }
})
const addItem = wrap(async () => {
  const body = { os: os.value.id, tipo: item.tipo, quantidade: item.quantidade }
  if (item.tipo === 'peca') body.peca = item.peca
  else { body.descricao = item.descricao; body.valor_unitario = item.valor_unitario || 0 }
  await api('/itens/', { method: 'POST', body })
  Object.assign(item, { peca: '', descricao: '', quantidade: 1, valor_unitario: '' })
  await carregar()
})
const delItem = wrap(async (id) => { await api(`/itens/${id}/`, { method: 'DELETE' }); await carregar() })
function editarItem(i) { itemEdit.id = i.id; itemEdit.quantidade = i.quantidade; itemEdit.valor_unitario = i.valor_unitario }
function cancelarItem() { itemEdit.id = null }
const salvarItem = wrap(async () => {
  await api(`/itens/${itemEdit.id}/`, { method: 'PATCH', body: { quantidade: itemEdit.quantidade, valor_unitario: itemEdit.valor_unitario } })
  cancelarItem(); await carregar()
})
const assinar = wrap(async (data) => { os.value = await api(`/os/${os.value.id}/assinar/`, { method: 'POST', body: { assinatura: data } }) })
function abrirCamera() { inputCamera.value?.click() }
function abrirGaleria() { inputGaleria.value?.click() }
async function subirFotos(e) {
  const arquivos = Array.from(e.target.files || [])
  e.target.value = ''
  if (!arquivos.length) return
  erro.value = ''; msg.value = ''
  enviandoFoto.value = true
  fotoTotal.value = arquivos.length
  const falhas = []
  let enviadas = 0
  try {
    for (let i = 0; i < arquivos.length; i++) {
      fotoAtual.value = i + 1
      let foto
      try {
        foto = await comprimirImagem(arquivos[i])
      } catch (err) {
        if (arquivos[i].size > LIMITE_FOTO_ORIGINAL) {
          const mb = (arquivos[i].size / (1024 * 1024)).toFixed(1)
          falhas.push(`Foto ${i + 1}: ${err.message} Ela tem ${mb} MB; o limite é 20 MB.`)
          continue
        }
        foto = arquivos[i]
      }
      try {
        const form = new FormData()
        form.append('os', os.value.id)
        form.append('imagem', foto)
        await api('/fotos/', { method: 'POST', form })
        enviadas++
      } catch (err) {
        falhas.push(`Foto ${i + 1}: ${err.message}`)
      }
    }
    if (enviadas) await carregar()
    if (falhas.length) erro.value = falhas.join(' · ')
    else msg.value = `${enviadas} foto${enviadas > 1 ? 's' : ''} enviada${enviadas > 1 ? 's' : ''}.`
  } finally {
    enviandoFoto.value = false
    fotoAtual.value = 0
    fotoTotal.value = 0
  }
}
const delFoto = wrap(async (id) => { await api(`/fotos/${id}/`, { method: 'DELETE' }); await carregar() })
async function atualizarFoto(f, dados) {
  erro.value = ''; msg.value = ''
  fotoSalvando.value = f.id
  try {
    const atual = await api(`/fotos/${f.id}/`, { method: 'PATCH', body: dados })
    Object.assign(f, atual)
    if (dados.visivel_cliente === true) msg.value = 'Foto visível no link do cliente.'
    else if (dados.visivel_cliente === false) msg.value = 'Foto ocultada do link do cliente.'
    else if ('tipo' in dados) msg.value = 'Tipo da foto atualizado.'
    else if ('legenda' in dados) msg.value = 'Legenda salva.'
  } catch (e) {
    erro.value = e.message
    await carregar()
  } finally {
    fotoSalvando.value = null
  }
}
const whatsapp = wrap(async () => { const r = await api(`/os/${os.value.id}/whatsapp/`); window.open(r.url, '_blank') })
const pdf = wrap(async () => { const b = await api(`/os/${os.value.id}/pdf/`, { blob: true }); window.open(URL.createObjectURL(b), '_blank') })
const pagar = wrap(async () => {
  const body = { forma: forma.value }
  if (valorPagamento.value !== '' && valorPagamento.value !== null) body.valor = valorPagamento.value
  os.value = await api(`/os/${os.value.id}/pagar/`, { method: 'POST', body })
  valorPagamento.value = ''; msg.value = 'Pagamento registrado no caixa.'
})
const excluir = wrap(async () => { if (confirm('Excluir esta OS? As peças voltam ao estoque.')) { await api(`/os/${os.value.id}/`, { method: 'DELETE' }); router.push('/os') } })
const linkPublico = computed(() => os.value ? `${location.origin}/r/${os.value.token}` : '')
</script>
<template>
  <div v-if="os">
    <div class="topo">
      <div><h1>OS #{{ os.numero }}</h1><span class="badge" :class="os.status">{{ os.status_label }}</span></div>
      <div class="acoes"><button class="btn wpp" @click="whatsapp">Enviar no WhatsApp</button><button class="btn sec" @click="pdf">PDF</button><RouterLink class="btn sec" :to="`/os/${os.id}/imprimir`">Imprimir</RouterLink></div>
    </div>
    <div v-if="erro" class="erro" role="alert">{{ erro }}</div><div v-if="msg" class="card" role="status">{{ msg }}</div>

    <div class="card">
      <h2>Andamento</h2>
      <div class="filtros"><button v-for="(l, k) in STATUS" :key="k" class="chip" :class="{ on: os.status === k }" @click="mudarStatus(k)">{{ l }}</button></div>
      <p class="mudo">Link do cliente: <a :href="linkPublico" target="_blank">{{ linkPublico }}</a></p>
    </div>

    <div class="card">
      <h2>{{ os.cliente_nome }}</h2>
      <p>{{ os.tipo_aparelho }} {{ os.marca }} {{ os.modelo }}<template v-if="os.numero_serie"> <span class="mudo">· Nº de série {{ os.numero_serie }}</span></template><template v-if="os.imei"> <span class="mudo">· IMEI {{ os.imei }}</span></template><br />
        <strong>Defeito:</strong> {{ os.defeito }}<br />
        <span class="mudo">Entrada {{ dataHoraBR(os.criado_em) }} · Previsão {{ dataBR(os.previsao_entrega) }}<template v-if="os.senha_aparelho"> · Senha: {{ os.senha_aparelho }}</template></span></p>
      <div v-if="os.checklist" class="checklist-texto">{{ os.checklist }}</div>
    </div>

    <div class="card">
      <h2>Peças e serviços</h2>
      <table v-if="os.itens.length">
        <thead><tr><th>Item</th><th class="r">Qtd</th><th class="r">Subtotal</th><th></th></tr></thead>
        <tbody>
          <tr v-for="i in os.itens" :key="i.id">
            <template v-if="itemEdit.id === i.id">
              <td>{{ i.descricao }}</td>
              <td colspan="2">
                <div class="acoes" style="align-items:center">
                  <label style="margin:0">Qtd<input v-model.number="itemEdit.quantidade" type="number" min="1" style="width:5rem" /></label>
                  <label style="margin:0">Valor unit. (R$)<input v-model="itemEdit.valor_unitario" type="number" step="0.01" min="0" style="width:7rem" /></label>
                </div>
              </td>
              <td class="r"><button class="chip" @click="salvarItem">Salvar</button> <button class="chip" @click="cancelarItem">Cancelar</button></td>
            </template>
            <template v-else>
              <td>{{ i.descricao }}</td>
              <td class="r">{{ i.quantidade }}</td>
              <td class="r">{{ brl(i.subtotal) }}</td>
              <td class="r"><button class="chip" @click="editarItem(i)">Editar</button> <button class="chip" @click="delItem(i.id)" :aria-label="`Remover ${i.descricao}`">Remover</button></td>
            </template>
          </tr>
        </tbody>
      </table>
      <form @submit.prevent="addItem" style="margin-top:1rem">
        <div class="linha2">
          <label>Tipo<select v-model="item.tipo"><option value="servico">Serviço</option><option value="peca">Peça do estoque</option></select></label>
          <label v-if="item.tipo === 'peca'">Peça<select v-model="item.peca" required><option value="" disabled>Escolha…</option><option v-for="p in pecas" :key="p.id" :value="p.id">{{ p.nome }} ({{ p.quantidade }} un · {{ brl(p.preco) }})</option></select></label>
          <label v-else>Descrição<input v-model="item.descricao" required /></label>
        </div>
        <div class="linha2">
          <label>Quantidade<input v-model.number="item.quantidade" type="number" min="1" /></label>
          <label v-if="item.tipo === 'servico'">Valor unitário<input v-model="item.valor_unitario" type="number" step="0.01" min="0" /></label>
        </div>
        <button class="btn sec">Adicionar item</button>
      </form>
      <hr style="border:0;border-top:1px solid var(--linha);margin:1rem 0" />
      <div class="linha2">
        <label>Desconto (R$)<input v-model="os.desconto" type="number" step="0.01" min="0" :disabled="auth.user?.cargo === 'tecnico'" /></label>
        <div><span class="mudo">Total</span><h1>{{ brl(os.total) }}</h1>
          <span class="mudo" v-if="admin">Custo {{ brl(os.custo) }} · Lucro {{ brl(os.lucro) }}</span></div>
      </div>
      <div class="campo-laudo">
        <label for="laudo">Laudo técnico</label>
        <div class="caixa-laudo">
          <textarea id="laudo" ref="inputLaudo" v-model="os.laudo"></textarea>
          <button type="button" class="chip btn-gerar-laudo" title="Gerar laudo automático" aria-label="Gerar laudo automático a partir do checklist e dos serviços" :disabled="gerandoLaudo" @click="gerarLaudo">🔄</button>
        </div>
      </div>
      <button class="btn" @click="salvarLaudo">Salvar laudo e desconto</button>
    </div>

    <div class="card">
      <h2>Fotos do aparelho</h2>
      <p class="mudo">Fotos marcadas como “Mostrar ao cliente” aparecem no link público da OS. Por isso, não mostre senhas, documentos ou dados pessoais na imagem.</p>
      <div class="fotos">
        <div v-for="f in os.fotos" :key="f.id" class="foto-item">
          <div class="foto-topo">
            <img :src="urlMidia(f.imagem)" alt="Foto do aparelho" />
            <svg v-if="f.visivel_cliente" class="icone-visivel" viewBox="0 0 24 24" width="17" height="17" role="img" aria-label="Visível no link do cliente">
              <title>Visível no link do cliente</title>
              <path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7S1 12 1 12z" fill="none" stroke="currentColor" stroke-width="2" />
              <circle cx="12" cy="12" r="3" fill="currentColor" />
            </svg>
          </div>
          <label class="mostrar-cliente"><input type="checkbox" :checked="f.visivel_cliente" :disabled="fotoSalvando === f.id" @change="atualizarFoto(f, { visivel_cliente: $event.target.checked })" /> Mostrar ao cliente</label>
          <label>Tipo
            <select v-model="f.tipo" :disabled="fotoSalvando === f.id" @change="atualizarFoto(f, { tipo: f.tipo })">
              <option value="entrada">Entrada</option>
              <option value="servico">Serviço</option>
            </select>
          </label>
          <label class="campo-legenda">Legenda
            <input v-model="f.legenda" maxlength="120" placeholder="Opcional" :disabled="fotoSalvando === f.id" @blur="atualizarFoto(f, { legenda: f.legenda })" />
          </label>
          <button class="chip" :disabled="fotoSalvando === f.id" @click="delFoto(f.id)">Remover</button>
        </div>
      </div>
      <div class="acoes" style="margin-top:.75rem">
        <button type="button" class="btn sec" :disabled="enviandoFoto" @click="abrirCamera">Tirar foto</button>
        <button type="button" class="btn sec" :disabled="enviandoFoto" @click="abrirGaleria">Escolher da galeria</button>
        <span class="mudo dica-camera">Se o celular fechar o navegador ao abrir a câmera, feche outros apps e abas ou diminua a resolução da câmera.</span>
      </div>
      <input ref="inputCamera" type="file" accept="image/*" capture="environment" style="display:none" @change="subirFotos" />
      <input ref="inputGaleria" type="file" accept="image/*" multiple style="display:none" @change="subirFotos" />
      <p v-if="enviandoFoto" class="mudo" role="status">Enviando foto {{ fotoAtual }} de {{ fotoTotal }}…</p>
      <p v-else class="mudo">As fotos são reduzidas no celular antes do envio. Na galeria você pode escolher várias.</p>
    </div>

    <div class="card">
      <h2>Assinatura do cliente</h2>
      <img v-if="os.assinatura" :src="urlMidia(os.assinatura)" alt="Assinatura" style="max-width:300px;border:1px solid var(--linha);border-radius:8px;background:#fff" />
      <p class="mudo" v-if="!os.assinatura">Peça para o cliente assinar com o dedo confirmando o estado do aparelho.</p>
      <Assinatura @salvar="assinar" />
    </div>

    <div class="card" v-if="restante > 0 && os.status !== 'cancelado'">
      <h2>Receber pagamento</h2>
      <p>Restante: <strong>{{ brl(restante) }}</strong></p>
      <div class="linha2">
        <label>Forma<select v-model="forma"><option value="pix">Pix</option><option value="dinheiro">Dinheiro</option><option value="debito">Débito</option><option value="credito">Crédito</option></select></label>
        <label>Valor a receber (R$)<input v-model="valorPagamento" type="number" step="0.01" min="0.01" :placeholder="String(restante)" /></label>
      </div>
      <p class="mudo">Deixe o valor em branco para receber o restante.</p>
      <button class="btn" @click="pagar">Registrar pagamento</button>
    </div>

    <button v-if="admin" class="btn perigo" @click="excluir">Excluir OS</button>
  </div>
</template>
<style scoped>
.foto-item { width: 11rem; padding: .5rem; border: 1px solid var(--linha); border-radius: 10px; background: #fff }
.foto-topo { position: relative }
.foto-item img { width: 100%; height: 8rem; object-fit: cover; border-radius: 8px; border: 1px solid var(--linha) }
.foto-item label { display: block; margin-top: .4rem; font-size: .8rem }
.foto-item .mostrar-cliente { display: flex; align-items: center; gap: .35rem; margin-top: .5rem }
.foto-item .campo-legenda input { width: 100% }
.foto-item .chip { margin-top: .5rem }
.icone-visivel { position: absolute; top: .3rem; right: .3rem; padding: 3px; border-radius: 50%; background: rgba(255, 255, 255, .92); color: #14543B }
.dica-camera { flex-basis: 100%; font-size: .75rem }
.checklist-texto { white-space: pre-line; padding: .6rem .75rem; border: 1px solid var(--linha); border-radius: 8px; background: #fff }
.campo-laudo { margin-top: 1rem }
.campo-laudo > label { display: block }
.caixa-laudo { position: relative }
.caixa-laudo textarea { padding-right: 3.25rem }
.btn-gerar-laudo { position: absolute; top: .55rem; right: .5rem; width: 36px; height: 36px; padding: 0; display: inline-flex; align-items: center; justify-content: center; font-size: 1.1rem; background: rgba(255, 255, 255, .94) }
.btn-gerar-laudo:disabled { opacity: .55; cursor: default }
</style>
