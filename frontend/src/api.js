import { reactive } from 'vue'

export const auth = reactive({
  access: localStorage.getItem('access') || '',
  refresh: localStorage.getItem('refresh') || '',
  user: JSON.parse(localStorage.getItem('user') || 'null'),
})

export function setSession({ access, refresh, usuario }) {
  if (access) { auth.access = access; localStorage.setItem('access', access) }
  if (refresh) { auth.refresh = refresh; localStorage.setItem('refresh', refresh) }
  if (usuario) { auth.user = usuario; localStorage.setItem('user', JSON.stringify(usuario)) }
}
export function logout() {
  auth.access = auth.refresh = ''; auth.user = null
  localStorage.clear()
  location.href = '/login'
}

async function renovar() {
  if (!auth.refresh) return { ok: false, status: 401 }
  let r
  try {
    r = await fetch('/api/auth/refresh/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ refresh: auth.refresh }) })
  } catch (e) {
    return { ok: false, status: 0, erro: e }  // erro de rede: não é culpa da sessão
  }
  if (!r.ok) return { ok: false, status: r.status }
  setSession(await r.json())
  return { ok: true }
}

// Renovação única: chamadas simultâneas compartilham a mesma tentativa, e a
// variável é limpa quando ela termina (evita disparar vários refresh iguais).
let renovando = null
function renovarUnico() {
  if (!renovando) renovando = renovar().finally(() => { renovando = null })
  return renovando
}

export async function api(path, { method = 'GET', body, form, blob } = {}, retry = true) {
  const headers = {}
  if (auth.access) headers.Authorization = `Bearer ${auth.access}`
  if (body) headers['Content-Type'] = 'application/json'
  const r = await fetch('/api' + path, { method, headers, body: form || (body ? JSON.stringify(body) : undefined) })
  // Não tenta renovar nas próprias rotas de autenticação (evita laço).
  const rotaAuth = path === '/auth/login/' || path === '/auth/refresh/'
  if (r.status === 401 && retry && auth.refresh && !rotaAuth) {
    const res = await renovarUnico()
    if (res.ok) return api(path, { method, body, form, blob }, false)
    if (res.status === 401 || res.status === 400) {
      logout()  // refresh inválido/expirado: a sessão acabou de verdade
    } else {
      // 429, 5xx ou erro de rede: não desloga; só avisa quem chamou.
      const erro = new Error('Não foi possível renovar a sessão. Tente novamente.')
      erro.status = res.status
      throw erro
    }
  }
  if (r.status === 204) return null
  if (!r.ok) {
    const data = await r.json().catch(() => null)
    const msg = data?.detail || (data && Object.entries(data).map(([k, v]) => (k === 'non_field_errors' ? '' : k + ': ') + [].concat(v).join(' ')).filter(Boolean).join(' | ')) || 'Erro inesperado'
    const erro = new Error(msg)
    erro.status = r.status
    throw erro
  }
  if (blob) return r.blob()
  return r.json().catch(() => null)
}

export const brl = (v) => Number(v || 0).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' })
export const dataBR = (d) => d ? new Date(d).toLocaleDateString('pt-BR') : '—'
export const dataHoraBR = (d) => d ? new Date(d).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' }) : '—'
export const STATUS = {
  orcamento: 'Orçamento', em_analise: 'Em análise', aguardando_peca: 'Aguardando peça',
  em_servico: 'Em serviço', finalizado: 'Finalizado', pago: 'Pago', cancelado: 'Cancelado',
}
