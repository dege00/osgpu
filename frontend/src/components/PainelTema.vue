<script setup>
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { contraste, hexValido } from '../utils/cores'
import {
  confirmarTema, descartarPrevia, desbloquear, enviarTema, estadoSalvo, mensagemDeErro, painel, previa,
  restaurarTema, TAMANHO_MAX, tema, urlTema,
} from '../composables/useTema'

const etapa = ref('senha')            // 'senha' | 'editor'
const senha = ref('')
const erro = ref('')
const ocupado = ref(false)
const raiz = ref(null)
let token = ''                        // só em memória: some ao fechar o painel
let focoAnterior = null

const rascunho = reactive({})
const arquivos = reactive({ logo: null, login_imagem: null, login_video: null })
const remover = reactive({ logo: false, login_imagem: false, login_video: false })
const previas = reactive({ logo: '', login_imagem: '', login_video: '' })

const VERTICAIS = [['topo', 'Topo'], ['meio', 'Meio'], ['base', 'Base']]
const HORIZONTAIS = [['esquerda', 'esquerda'], ['centro', 'centro'], ['direita', 'direita']]
const CAMPOS_ENVIO = ['cor_menu', 'cor_destaque', 'login_fundo_tipo', 'login_cor', 'caixa_vertical', 'caixa_horizontal', 'caixa_opacidade']

const avisos = computed(() => {
  const a = []
  if (hexValido(rascunho.cor_destaque) && contraste(rascunho.cor_destaque, '#FFFFFF') < 1.8)
    a.push('A cor de destaque é muito clara: botões e links podem sumir no fundo branco.')
  if (hexValido(rascunho.cor_menu) && contraste(rascunho.cor_menu, '#F3F4EF') < 1.3)
    a.push('A cor do menu é quase igual à do fundo das telas, e o menu pode se confundir com elas.')
  return a
})

function limparPrevias() {
  for (const k of Object.keys(previas)) { if (previas[k].startsWith('blob:')) URL.revokeObjectURL(previas[k]); previas[k] = '' }
  for (const k of Object.keys(arquivos)) { arquivos[k] = null; remover[k] = false }
}

function reiniciar() {
  limparPrevias()
  descartarPrevia()
  etapa.value = 'senha'; senha.value = ''; erro.value = ''; token = ''
}

function abrirEditor() {
  Object.assign(rascunho, Object.fromEntries(CAMPOS_ENVIO.map((c) => [c, estadoSalvo()[c]])))
  etapa.value = 'editor'; erro.value = ''
  focarPrimeiro()
}

function aplicarPrevia() {
  if (etapa.value !== 'editor') return
  const base = estadoSalvo()
  const mostrar = (campo) => (remover[campo] ? '' : previas[campo] || base[campo])
  previa({ ...rascunho, logo: mostrar('logo'), login_imagem: mostrar('login_imagem'), login_video: mostrar('login_video') })
}
watch([rascunho, previas, remover], aplicarPrevia, { deep: true })

async function focarPrimeiro() {
  await nextTick()
  raiz.value?.querySelector('input:not([type=hidden]), button')?.focus()
}

watch(() => painel.aberto, (aberto) => {
  if (aberto) { focoAnterior = document.activeElement; reiniciar(); focarPrimeiro() }
  else focoAnterior?.focus?.()
})

function fechar(descartar = true) {
  if (descartar) descartarPrevia()
  reiniciar()
  painel.aberto = false
}

function mensagem404(data) {
  if (data?.codigo === 'painel_desativado')
    return 'O painel não está ativado neste servidor. Defina PAINEL_TEMA_SENHA_HASH (veja o README) e reinicie o backend.'
  return 'O servidor não reconhece o painel de tema: o backend está desatualizado. Atualize o código, rode `python manage.py migrate` e reinicie o backend.'
}

function teclas(e) {
  if (e.key === 'Escape') { e.preventDefault(); fechar(); return }
  if (e.key !== 'Tab') return
  const itens = [...raiz.value.querySelectorAll('button, input, select, textarea, [tabindex]:not([tabindex="-1"])')]
    .filter((el) => !el.disabled && el.offsetParent !== null)
  if (!itens.length) return
  const [primeiro, ultimo] = [itens[0], itens[itens.length - 1]]
  if (e.shiftKey && document.activeElement === primeiro) { e.preventDefault(); ultimo.focus() }
  else if (!e.shiftKey && document.activeElement === ultimo) { e.preventDefault(); primeiro.focus() }
}

async function entrar() {
  erro.value = ''; ocupado.value = true
  const r = await desbloquear(senha.value)
  ocupado.value = false
  if (r.ok) { token = r.data.token; senha.value = ''; abrirEditor(); return }
  if (r.status === 429) erro.value = 'Muitas tentativas. Aguarde um minuto e tente de novo.'
  else if (r.status === 404) erro.value = mensagem404(r.data)
  else if (r.status >= 500) erro.value = 'Erro no servidor. Se acabou de atualizar o sistema, rode `python manage.py migrate` e reinicie o backend; veja o log para detalhes.'
  else erro.value = mensagemDeErro(r.data)
  senha.value = ''
}

function escolher(campo, evento) {
  const arquivo = evento.target.files?.[0]
  if (!arquivo) return
  const limite = TAMANHO_MAX[campo]
  if (arquivo.size > limite * 1024 * 1024) {
    erro.value = `O arquivo é grande demais (máximo ${limite} MB).`; evento.target.value = ''; return
  }
  erro.value = ''
  if (previas[campo].startsWith('blob:')) URL.revokeObjectURL(previas[campo])
  arquivos[campo] = arquivo
  previas[campo] = URL.createObjectURL(arquivo)
  remover[campo] = false
}

function faltaArquivo() {
  const base = estadoSalvo()
  for (const [tipo, campo] of [['imagem', 'login_imagem'], ['video', 'login_video']]) {
    if (rascunho.login_fundo_tipo === tipo && !arquivos[campo] && (!base[campo] || remover[campo]))
      return `Escolha ${tipo === 'imagem' ? 'uma imagem' : 'um vídeo'} para usar como fundo.`
  }
  return ''
}

function tratarFalha(r) {
  if (r.status === 403 && /Sess/.test(r.data?.detail || '')) {
    reiniciar()
    erro.value = 'Sessão do painel expirada. Entre de novo.'
    return
  }
  if (r.status === 404) erro.value = mensagem404(r.data)
  else if (r.status >= 500) erro.value = 'Erro no servidor. Se acabou de atualizar o sistema, rode `python manage.py migrate` e reinicie o backend; veja o log para detalhes.'
  else erro.value = mensagemDeErro(r.data)
}

async function salvar() {
  erro.value = faltaArquivo()
  if (erro.value) return
  const f = new FormData()
  CAMPOS_ENVIO.forEach((c) => f.append(c, rascunho[c]))
  Object.entries(arquivos).forEach(([c, a]) => a && f.append(c, a))
  Object.entries(remover).forEach(([c, v]) => v && f.append(`remover_${c}`, '1'))
  ocupado.value = true
  const r = await enviarTema(f, token)
  ocupado.value = false
  if (!r.ok) return tratarFalha(r)
  confirmarTema(r.data)
  fechar(false)
}

async function restaurar() {
  if (!confirm('Voltar o logo, as cores e a tela de login ao padrão?')) return
  ocupado.value = true
  const r = await restaurarTema(token)
  ocupado.value = false
  if (!r.ok) return tratarFalha(r)
  confirmarTema(r.data)
  fechar(false)
}

onBeforeUnmount(limparPrevias)
</script>

<template>
  <Teleport to="body">
    <div v-if="painel.aberto" class="tema-fundo" @click.self="fechar()" @keydown="teclas">
      <div ref="raiz" class="tema-painel" role="dialog" aria-modal="true" aria-labelledby="tema-titulo">
        <form v-if="etapa === 'senha'" @submit.prevent="entrar">
          <h2 id="tema-titulo">Painel do sistema</h2>
          <div v-if="erro" class="erro" role="alert">{{ erro }}</div>
          <label>Senha<input v-model="senha" type="password" autocomplete="off" required /></label>
          <div class="acoes">
            <button class="btn" :disabled="ocupado">Entrar</button>
            <button type="button" class="btn sec" @click="fechar()">Cancelar</button>
          </div>
        </form>

        <form v-else @submit.prevent="salvar">
          <h2 id="tema-titulo">Personalizar o sistema</h2>
          <p class="mudo">Vale para todas as assistências. A prévia é ao vivo e só é gravada quando você salvar.</p>
          <div v-if="erro" class="erro" role="alert">{{ erro }}</div>
          <div v-for="aviso in avisos" :key="aviso" class="tema-aviso" role="status">{{ aviso }}</div>

          <fieldset>
            <legend>Logo</legend>
            <img v-if="urlTema(tema.logo)" :src="tema.logo" alt="Logo atual" class="tema-logo-previa" />
            <label>Enviar nova logo (PNG, JPG ou WEBP, até {{ TAMANHO_MAX.logo }} MB)
              <input type="file" accept="image/png,image/jpeg,image/webp" @change="escolher('logo', $event)" /></label>
            <label class="tema-opcao"><input v-model="remover.logo" type="checkbox" /> Remover a logo (voltar ao ícone padrão)</label>
          </fieldset>

          <fieldset>
            <legend>Cores do sistema</legend>
            <div class="linha2">
              <label>Menu e destaques escuros<input v-model="rascunho.cor_menu" type="color" /></label>
              <label>Botões e links<input v-model="rascunho.cor_destaque" type="color" /></label>
            </div>
          </fieldset>

          <fieldset>
            <legend>Fundo da tela de login</legend>
            <div class="tema-abas" role="radiogroup" aria-label="Tipo de fundo">
              <label v-for="[valor, nome] in [['cor', 'Cor sólida'], ['imagem', 'Imagem'], ['video', 'Vídeo']]" :key="valor" class="tema-opcao">
                <input v-model="rascunho.login_fundo_tipo" type="radio" name="fundo" :value="valor" /> {{ nome }}
              </label>
            </div>
            <label v-if="rascunho.login_fundo_tipo === 'cor'">Cor do fundo<input v-model="rascunho.login_cor" type="color" /></label>
            <template v-else-if="rascunho.login_fundo_tipo === 'imagem'">
              <label>Papel de parede (PNG, JPG ou WEBP, até {{ TAMANHO_MAX.login_imagem }} MB)
                <input type="file" accept="image/png,image/jpeg,image/webp" @change="escolher('login_imagem', $event)" /></label>
              <label class="tema-opcao"><input v-model="remover.login_imagem" type="checkbox" /> Remover a imagem salva</label>
            </template>
            <template v-else>
              <label>Vídeo (MP4 ou WEBM, até {{ TAMANHO_MAX.login_video }} MB)
                <input type="file" accept="video/mp4,video/webm" @change="escolher('login_video', $event)" /></label>
              <p class="mudo">Toca sem som e em repetição. É desligado em modo de economia de dados e para quem prefere menos animação.</p>
              <label class="tema-opcao"><input v-model="remover.login_video" type="checkbox" /> Remover o vídeo salvo</label>
            </template>
          </fieldset>

          <fieldset>
            <legend>Posição da caixa de login</legend>
            <div class="tema-posicoes" role="radiogroup" aria-label="Posição da caixa de login">
              <template v-for="[v, nomeV] in VERTICAIS" :key="v">
                <button v-for="[h, nomeH] in HORIZONTAIS" :key="v + h" type="button" role="radio"
                  :aria-checked="rascunho.caixa_vertical === v && rascunho.caixa_horizontal === h"
                  :aria-label="`${nomeV} ${nomeH}`" class="tema-posicao"
                  :class="{ ativa: rascunho.caixa_vertical === v && rascunho.caixa_horizontal === h }"
                  @click="rascunho.caixa_vertical = v; rascunho.caixa_horizontal = h"></button>
              </template>
            </div>
            <p class="mudo">Em telas pequenas a caixa fica sempre no centro.</p>
            <label>Transparência da caixa: {{ rascunho.caixa_opacidade }}%
              <input v-model.number="rascunho.caixa_opacidade" type="range" min="60" max="100" step="5" /></label>
          </fieldset>

          <div class="acoes">
            <button class="btn" :disabled="ocupado">{{ ocupado ? 'Salvando…' : 'Salvar' }}</button>
            <button type="button" class="btn sec" :disabled="ocupado" @click="fechar()">Cancelar</button>
            <button type="button" class="btn perigo" :disabled="ocupado" @click="restaurar">Restaurar padrão</button>
          </div>
        </form>
      </div>
    </div>
  </Teleport>
</template>

<style>
.tema-fundo { position: fixed; inset: 0; z-index: 1000; background: rgb(0 0 0 / .55); display: grid; place-items: center; padding: 1rem }
.tema-painel { background: #fff; color: #13201C; width: min(520px, 100%); max-height: 92dvh; overflow-y: auto; border-radius: 12px; padding: 1.25rem; box-shadow: 0 20px 60px rgb(0 0 0 / .4) }
.tema-painel fieldset { border: 1px solid var(--linha); border-radius: 10px; margin: 0 0 1rem; padding: .75rem 1rem }
.tema-painel legend { font: 700 .95rem var(--font-titulo); padding: 0 .4rem }
.tema-painel input[type=color] { height: 2.5rem; padding: .15rem; cursor: pointer }
.tema-painel input[type=range] { padding: 0 }
.tema-opcao { display: flex; align-items: center; gap: .5rem; font-weight: 400; margin-bottom: .5rem }
.tema-opcao input { width: auto; margin: 0 }
.tema-abas { display: flex; gap: 1rem; flex-wrap: wrap; margin-bottom: .5rem }
.tema-logo-previa { display: block; width: 64px; height: 64px; object-fit: contain; border: 1px solid var(--linha); border-radius: 8px; margin-bottom: .5rem; background: repeating-conic-gradient(#eee 0 25%, #fff 0 50%) 0 0 / 12px 12px }
.tema-posicoes { display: grid; grid-template-columns: repeat(3, 1fr); gap: .35rem; width: 168px; padding: .5rem; border: 1px solid var(--linha); border-radius: 8px; background: #F3F4EF; margin-bottom: .5rem }
.tema-posicao { height: 36px; border-radius: 6px; border: 1px solid #B9BFB3; background: #fff; cursor: pointer; padding: 0 }
.tema-posicao.ativa { background: var(--acento-texto); border-color: var(--acento-texto) }
.tema-aviso { background: #FFF4D6; color: #5B4300; border: 1px solid #E8CC7A; padding: .5rem .75rem; border-radius: 8px; margin-bottom: .75rem; font-size: .9rem }
</style>
