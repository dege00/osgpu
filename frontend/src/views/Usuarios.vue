<script setup>
import { onMounted, reactive, ref } from 'vue'
import { api, auth } from '../api'

const CARGO = { admin: 'Administrador', atendente: 'Atendente', tecnico: 'Técnico' }
const lista = ref([]), erro = ref(''), msg = ref(''), editando = ref(null), salvando = ref(false)
const vazio = () => ({ first_name: '', username: '', email: '', telefone: '', cargo: 'atendente', senha: '' })
const f = reactive(vazio())

const carregar = async () => {
  try { lista.value = (await api('/usuarios/?page_size=200')).results } catch (e) { erro.value = e.message }
}
onMounted(carregar)

function editar(u) {
  editando.value = u.id
  Object.assign(f, vazio(), {
    first_name: u.first_name || '', username: u.username, email: u.email || '',
    telefone: u.telefone || '', cargo: u.cargo, senha: '',
  })
  window.scrollTo(0, 0)
}
function cancelar() { editando.value = null; Object.assign(f, vazio()) }

async function salvar() {
  erro.value = ''; msg.value = ''; salvando.value = true
  try {
    const body = { ...f }
    if (editando.value && !body.senha) delete body.senha
    await api(editando.value ? `/usuarios/${editando.value}/` : '/usuarios/', {
      method: editando.value ? 'PATCH' : 'POST', body,
    })
    msg.value = editando.value ? 'Usuário atualizado.' : 'Usuário criado.'
    cancelar(); carregar()
  } catch (e) { erro.value = e.message } finally { salvando.value = false }
}

async function alternar(u) {
  erro.value = ''; msg.value = ''
  try {
    await api(`/usuarios/${u.id}/`, { method: 'PATCH', body: { is_active: !u.is_active } })
    msg.value = u.is_active ? 'Usuário desativado.' : 'Usuário ativado.'
    carregar()
  } catch (e) { erro.value = e.message }
}
</script>

<template>
  <h1>Usuários da assistência</h1>
  <div v-if="erro" class="erro" role="alert">{{ erro }}</div>
  <div v-if="msg" class="card" role="status">{{ msg }}</div>

  <form class="card" @submit.prevent="salvar">
    <h2>{{ editando ? 'Editar usuário' : 'Novo usuário' }}</h2>
    <div class="linha2">
      <label>Nome<input v-model="f.first_name" required /></label>
      <label>Usuário de acesso<input v-model="f.username" autocomplete="off" required /></label>
    </div>
    <div class="linha2">
      <label>Cargo
        <select v-model="f.cargo">
          <option v-for="(rotulo, valor) in CARGO" :key="valor" :value="valor">{{ rotulo }}</option>
        </select>
      </label>
      <label>WhatsApp<input v-model="f.telefone" inputmode="tel" /></label>
    </div>
    <div class="linha2">
      <label>E-mail<input v-model="f.email" type="email" /></label>
      <label>{{ editando ? 'Nova senha (deixe em branco para manter)' : 'Senha inicial' }}
        <input v-model="f.senha" type="password" minlength="8" :required="!editando" autocomplete="new-password" />
      </label>
    </div>
    <div class="acoes">
      <button class="btn" :disabled="salvando">{{ editando ? 'Salvar alterações' : 'Criar usuário' }}</button>
      <button v-if="editando" type="button" class="btn sec" @click="cancelar">Cancelar</button>
    </div>
  </form>

  <ul class="lista">
    <li v-for="u in lista" :key="u.id">
      <div>
        <strong>{{ u.first_name || u.username }}</strong>
        <span v-if="u.id === auth.user?.id" class="badge">você</span>
        <span v-if="!u.is_active" class="badge cancelado">desativado</span><br />
        <span class="mudo">{{ u.username }} · {{ CARGO[u.cargo] }}{{ u.telefone ? ' · ' + u.telefone : '' }}</span>
      </div>
      <div class="acoes">
        <button class="chip" @click="editar(u)">Editar</button>
        <button v-if="u.id !== auth.user?.id" class="chip" @click="alternar(u)">{{ u.is_active ? 'Desativar' : 'Ativar' }}</button>
      </div>
    </li>
  </ul>
  <p v-if="!lista.length" class="vazio">Nenhum usuário cadastrado.</p>
</template>
