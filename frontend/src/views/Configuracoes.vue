<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api, auth, setSession } from '../api'
import { urlMidia } from '../utils/midia'

const f = reactive({ nome: '', telefone: '', documento: '', endereco: '', termo_garantia: '' })
const erro = ref(''), msg = ref(''), salvando = ref(false)
const logoAtual = ref(''), arquivoLogo = ref(null)

const senha = reactive({ atual: '', nova: '', confirma: '' })
const senhaErro = ref(''), senhaMsg = ref(''), trocando = ref(false)

const exportando = ref(''), exportarErro = ref('')

async function carregar() {
  try {
    const u = await api('/auth/eu/')
    setSession({ usuario: u })
    Object.assign(f, {
      nome: u.loja?.nome || '', telefone: u.loja?.telefone || '', documento: u.loja?.documento || '',
      endereco: u.loja?.endereco || '', termo_garantia: u.loja?.termo_garantia || '',
    })
    logoAtual.value = u.loja?.logo || ''
  } catch (e) { erro.value = e.message }
}
onMounted(carregar)

let urlLogo = ''
function escolherLogo(e) {
  const file = e.target.files[0]
  arquivoLogo.value = file || null
  if (urlLogo) URL.revokeObjectURL(urlLogo)
  urlLogo = file ? URL.createObjectURL(file) : ''
  if (urlLogo) logoAtual.value = urlLogo
}

async function salvar() {
  erro.value = ''; msg.value = ''; salvando.value = true
  try {
    const form = new FormData()
    for (const [k, v] of Object.entries(f)) form.append(k, v ?? '')
    if (arquivoLogo.value) form.append('logo', arquivoLogo.value)
    const u = await api('/auth/eu/', { method: 'PATCH', form })
    setSession({ usuario: u })
    logoAtual.value = u.loja?.logo || logoAtual.value
    if (urlLogo) URL.revokeObjectURL(urlLogo)
    urlLogo = ''
    arquivoLogo.value = null
    msg.value = 'Dados da assistência salvos.'
  } catch (e) { erro.value = e.message } finally { salvando.value = false }
}

async function trocarSenha() {
  senhaErro.value = ''; senhaMsg.value = ''
  if (senha.nova !== senha.confirma) { senhaErro.value = 'A confirmação não confere com a nova senha.'; return }
  trocando.value = true
  try {
    const t = await api('/auth/trocar-senha/', { method: 'POST', body: { senha_atual: senha.atual, nova_senha: senha.nova } })
    setSession({ access: t.access, refresh: t.refresh })  // mantém esta sessão ativa com o par novo
    senhaMsg.value = 'Senha alterada com sucesso.'
    senha.atual = senha.nova = senha.confirma = ''
  } catch (e) { senhaErro.value = e.message } finally { trocando.value = false }
}

async function exportar(tipo) {
  exportarErro.value = ''; exportando.value = tipo
  try {
    const blob = await api(`/exportar/${tipo}/`, { blob: true })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${tipo}-${new Date().toISOString().slice(0, 10)}.xlsx`
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
  } catch (e) { exportarErro.value = e.message } finally { exportando.value = '' }
}
</script>

<template>
  <h1>Configurações da assistência</h1>
  <div v-if="erro" class="erro" role="alert">{{ erro }}</div>
  <div v-if="msg" class="card" role="status">{{ msg }}</div>

  <form class="card" @submit.prevent="salvar">
    <h2>Dados que aparecem na OS e no PDF</h2>
    <label>Nome da assistência<input v-model="f.nome" required /></label>
    <div class="linha2">
      <label>WhatsApp / telefone<input v-model="f.telefone" inputmode="tel" /></label>
      <label>CNPJ / CPF<input v-model="f.documento" /></label>
    </div>
    <label>Endereço<input v-model="f.endereco" /></label>
    <label>Termo de garantia<textarea v-model="f.termo_garantia" placeholder="Ex.: Garantia de 90 dias sobre o serviço executado."></textarea></label>

    <label>Logotipo (usado no PDF)
      <input type="file" accept="image/*" @change="escolherLogo" />
    </label>
    <p v-if="logoAtual" class="mudo"><img :src="urlMidia(logoAtual)" alt="Logotipo atual" style="max-width:160px;max-height:80px;border:1px solid var(--linha);border-radius:8px;background:#fff;padding:.25rem" /></p>

    <button class="btn" :disabled="salvando">{{ salvando ? 'Salvando…' : 'Salvar configurações' }}</button>
  </form>

  <form class="card" @submit.prevent="trocarSenha">
    <h2>Minha senha</h2>
    <div v-if="senhaErro" class="erro" role="alert">{{ senhaErro }}</div>
    <div v-if="senhaMsg" class="card" role="status">{{ senhaMsg }}</div>
    <label>Senha atual<input v-model="senha.atual" type="password" autocomplete="current-password" required /></label>
    <label>Nova senha<input v-model="senha.nova" type="password" autocomplete="new-password" required /></label>
    <label>Confirmar nova senha<input v-model="senha.confirma" type="password" autocomplete="new-password" required /></label>
    <button class="btn" :disabled="trocando">{{ trocando ? 'Alterando…' : 'Alterar senha' }}</button>
  </form>

  <section v-if="auth.user?.cargo === 'admin'" class="card">
    <h2>Exportar dados</h2>
    <p class="mudo">Baixe uma planilha Excel (.xlsx) com os dados da sua assistência.</p>
    <div v-if="exportarErro" class="erro" role="alert">{{ exportarErro }}</div>
    <div class="linha2">
      <button class="btn" type="button" :disabled="!!exportando" @click="exportar('clientes')">
        {{ exportando === 'clientes' ? 'Gerando…' : 'Baixar clientes (.xlsx)' }}
      </button>
      <button class="btn" type="button" :disabled="!!exportando" @click="exportar('pecas')">
        {{ exportando === 'pecas' ? 'Gerando…' : 'Baixar produtos (.xlsx)' }}
      </button>
    </div>
  </section>
</template>
