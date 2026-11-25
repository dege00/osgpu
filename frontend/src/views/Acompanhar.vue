<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { brl, dataBR, dataHoraBR } from '../api'
import { urlMidia } from '../utils/midia'
const d = ref(null), erro = ref(''), ampliada = ref(null)
const FLUXO = [['em_analise', 'Em análise'], ['aguardando_peca', 'Aguardando peça'], ['em_servico', 'Em serviço'], ['finalizado', 'Finalizado'], ['pago', 'Pago e entregue']]
const TIPO_FOTO = { entrada: 'Entrada', servico: 'Serviço' }
onMounted(async () => {
  const r = await fetch(`/api/publico/os/${useRoute().params.token}/`)
  if (r.ok) d.value = await r.json(); else erro.value = 'Não encontramos essa ordem de serviço. Confira o link.'
})
const idx = computed(() => FLUXO.findIndex(([k]) => k === d.value?.status))
const wpp = computed(() => d.value?.loja_telefone ? `https://wa.me/55${d.value.loja_telefone.replace(/\D/g, '').replace(/^55/, '')}` : null)
</script>
<template>
  <div class="centro"><div class="caixa card">
    <p v-if="erro" class="erro">{{ erro }}</p>
    <template v-if="d">
      <p class="mudo" style="margin:0">{{ d.loja }}</p>
      <h1>OS #{{ d.numero }}</h1>
      <p>Olá, {{ d.cliente }}. Aqui está o andamento do seu <strong>{{ d.aparelho }}</strong>.</p>
      <ul class="linha-tempo" v-if="d.status !== 'cancelado' && d.status !== 'orcamento'">
        <li v-for="([k, l], i) in FLUXO" :key="k" :class="{ feito: i < idx, atual: i === idx }">
          <strong>{{ l }}</strong>
          <div class="mudo" v-if="d.historico.find(h => h.status === k)">{{ dataHoraBR(d.historico.find(h => h.status === k).em) }}</div>
        </li>
      </ul>
      <p v-else><span class="badge" :class="d.status">{{ d.status_label }}</span></p>
      <p v-if="d.previsao_entrega" class="mudo">Previsão de entrega: {{ dataBR(d.previsao_entrega) }}</p>
      <table v-if="d.itens.length"><tbody><tr v-for="(i, n) in d.itens" :key="n"><td>{{ i.descricao }}</td><td class="r">{{ brl(i.subtotal) }}</td></tr>
        <tr><td><strong>Total</strong></td><td class="r"><strong>{{ brl(d.total) }}</strong></td></tr></tbody></table>
      <p v-if="d.status === 'finalizado'">Seu aparelho está pronto para retirada.</p>
      <section v-if="d.fotos?.length" class="fotos-cliente">
        <h2>Fotos do seu aparelho</h2>
        <div class="grade-fotos">
          <button v-for="(f, n) in d.fotos" :key="n" type="button" class="foto-publica" @click="ampliada = f">
            <img :src="urlMidia(f.url)" :alt="f.legenda || 'Foto do aparelho'" loading="lazy" />
            <span class="tag">{{ TIPO_FOTO[f.tipo] || f.tipo }}</span>
            <span v-if="f.legenda" class="legenda">{{ f.legenda }}</span>
          </button>
        </div>
      </section>
      <a v-if="wpp" :href="wpp" class="btn wpp" style="margin-top:.75rem" target="_blank">Falar com a loja</a>
    </template>
  </div></div>
  <div v-if="ampliada" class="lightbox" role="dialog" aria-modal="true" @click.self="ampliada = null">
    <img :src="urlMidia(ampliada.url)" :alt="ampliada.legenda || 'Foto do aparelho'" />
    <p v-if="ampliada.legenda">{{ ampliada.legenda }}</p>
    <button type="button" class="btn sec" @click="ampliada = null">Fechar</button>
  </div>
</template>
<style scoped>
.fotos-cliente { margin-top: 1.25rem }
.grade-fotos { display: grid; grid-template-columns: repeat(auto-fill, minmax(110px, 1fr)); gap: .5rem }
.foto-publica { position: relative; display: block; padding: 0; overflow: hidden; border: 1px solid var(--linha); border-radius: 9px; background: #fff; cursor: zoom-in; text-align: left; font: inherit }
.foto-publica img { display: block; width: 100%; aspect-ratio: 1; object-fit: cover }
.foto-publica .tag { position: absolute; top: .35rem; left: .35rem; padding: .05rem .35rem; border-radius: 99px; background: rgba(19, 32, 28, .78); color: #fff; font-size: .68rem }
.foto-publica .legenda { display: block; padding: .35rem; font-size: .75rem; line-height: 1.2; color: var(--ink-2) }
.lightbox { position: fixed; inset: 0; z-index: 1000; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: .75rem; padding: 1rem; background: rgba(0, 0, 0, .88) }
.lightbox img { max-width: 100%; max-height: 82dvh; object-fit: contain; border-radius: 6px }
.lightbox p { margin: 0; color: #fff; text-align: center }
</style>
