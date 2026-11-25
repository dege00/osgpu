// Tema global do sistema (logo, cores e tela de login). Leitura pública; escrita só pelo painel com senha.
import { reactive } from 'vue'
import { hexValido, PADRAO_TEMA, VARIAVEIS, variaveisDoTema } from '../utils/cores'

const CHAVE_CACHE = 'tema_cache'
const CAMPOS_COR = ['cor_menu', 'cor_destaque', 'login_cor']

export const tema = reactive({ ...PADRAO_TEMA })   // estado vivo (inclui a prévia do painel)
export const painel = reactive({ aberto: false })
let salvo = { ...PADRAO_TEMA }                      // último estado confirmado pelo servidor

export const TAMANHO_MAX = { logo: 2, login_imagem: 10, login_video: 10 }   // em MB

/** Só aceita mídia do próprio servidor (ou prévia local); nunca uma URL externa. */
export const urlTema = (u) => (typeof u === 'string' && (u.startsWith('/media/') || u.startsWith('blob:')) ? u : '')

function limpar(dados) {
  const t = { ...PADRAO_TEMA, ...dados }
  for (const c of CAMPOS_COR) if (!hexValido(t[c])) t[c] = PADRAO_TEMA[c]
  for (const c of ['logo', 'login_imagem', 'login_video']) t[c] = urlTema(t[c])
  return t
}

export function aplicarTema() {
  const raiz = document.documentElement.style
  const padrao = tema.cor_menu === PADRAO_TEMA.cor_menu && tema.cor_destaque === PADRAO_TEMA.cor_destaque
  if (padrao) VARIAVEIS.forEach((v) => raiz.removeProperty(v))   // sem tema: valem os padrões do style.css
  else Object.entries(variaveisDoTema(tema)).forEach(([k, v]) => raiz.setProperty(k, v))
  document.querySelector('meta[name="theme-color"]')?.setAttribute('content', tema.cor_menu)
}

function definirSalvo(dados) {
  const t = limpar(dados)
  Object.assign(tema, t)
  salvo = t
  try { localStorage.setItem(CHAVE_CACHE, JSON.stringify(t)) } catch { /* cache é só conveniência */ }
  aplicarTema()
}

export async function carregarTema() {
  try {
    const r = await fetch('/api/tema/', { cache: 'no-cache' })   // sem Authorization: é público
    if (r.ok) definirSalvo(await r.json())
  } catch { /* sem rede: segue com o cache ou o padrão */ }
}

/** Aplica o cache na hora (evita piscar a cor antiga) e atualiza pelo servidor em segundo plano. */
export function iniciarTema() {
  try {
    const cache = JSON.parse(localStorage.getItem(CHAVE_CACHE) || 'null')
    if (cache) { const t = limpar(cache); Object.assign(tema, t); salvo = t }
  } catch { /* cache inválido: ignora */ }
  aplicarTema()
  carregarTema()
}

export const estadoSalvo = () => ({ ...salvo })
export function previa(parcial) { Object.assign(tema, limpar({ ...tema, ...parcial })); aplicarTema() }
export function descartarPrevia() { Object.assign(tema, salvo); aplicarTema() }
export const confirmarTema = definirSalvo

async function chamar(caminho, opcoes) {
  try {
    const r = await fetch(caminho, opcoes)
    return { ok: r.ok, status: r.status, data: await r.json().catch(() => ({})) }
  } catch {
    return { ok: false, status: 0, data: { detail: 'Sem conexão com o servidor.' } }
  }
}

export const desbloquear = (senha) => chamar('/api/tema/desbloquear/', {
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ senha }),
})
export const enviarTema = (formData, token) => chamar('/api/tema/', { method: 'PATCH', headers: { 'X-Tema-Token': token }, body: formData })
export const restaurarTema = (token) => chamar('/api/tema/restaurar/', { method: 'POST', headers: { 'X-Tema-Token': token } })

export function mensagemDeErro(data) {
  if (data?.detail) return data.detail
  const partes = Object.values(data || {}).flat().filter((x) => typeof x === 'string')
  return partes.join(' ') || 'Não foi possível concluir. Tente de novo.'
}
