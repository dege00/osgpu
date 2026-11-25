<script setup>
import { computed, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { api, setSession } from '../api'
import LogoSecreta from '../components/LogoSecreta.vue'
import { tema, urlTema } from '../composables/useTema'
const router = useRouter()
const erro = ref(''), carregando = ref(false)
const f = reactive({ username: '', senha: '' })

// Fundo da tela de login (definido no painel de tema). O vídeo não carrega com "economia de dados" ou "menos animação".
const evitarVideo = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches || navigator.connection?.saveData === true
const videoFalhou = ref(false)
const urlVideo = computed(() => urlTema(tema.login_video))
const usarVideo = computed(() => tema.login_fundo_tipo === 'video' && urlVideo.value && !evitarVideo && !videoFalhou.value)
const fundo = computed(() => {
  const estilo = { backgroundColor: tema.login_cor }
  const imagem = urlTema(tema.login_imagem)
  if (tema.login_fundo_tipo === 'imagem' && imagem) Object.assign(estilo, { backgroundImage: `url("${imagem}")`, backgroundSize: 'cover', backgroundPosition: 'center' })
  return estilo
})
async function entrar() {
  erro.value = ''; carregando.value = true
  try {
    const t = await api('/auth/login/', { method: 'POST', body: { username: f.username, password: f.senha } })
    setSession(t)
    setSession({ usuario: await api('/auth/eu/') })
    router.push('/')
  } catch (e) {
    if (e.status === 429) erro.value = 'Muitas tentativas. Aguarde um minuto e tente de novo.'
    else erro.value = e.message === 'No active account found with the given credentials' ? 'Usuário ou senha incorretos.' : e.message
  } finally { carregando.value = false }
}
</script>
<template>
  <div class="login-pagina" :class="[`v-${tema.caixa_vertical}`, `h-${tema.caixa_horizontal}`]" :style="fundo">
    <video v-if="usarVideo" class="login-video" :src="urlVideo" autoplay muted loop playsinline preload="metadata"
      disablepictureinpicture aria-hidden="true" @error="videoFalhou = true"></video>
    <form class="card caixa login-caixa" :style="{ '--caixa-op': tema.caixa_opacidade / 100 }" @submit.prevent="entrar">
      <LogoSecreta :tamanho="56" class="login-logo" />
      <h1>Entrar</h1>
      <p class="mudo">Ordens de serviço, estoque e caixa no celular.</p>
      <div v-if="erro" class="erro" role="alert">{{ erro }}</div>
      <label>Usuário<input v-model="f.username" autocomplete="username" required /></label>
      <label>Senha<input v-model="f.senha" type="password" autocomplete="current-password" required /></label>
      <button class="btn" style="width:100%" :disabled="carregando">Entrar</button>
    </form>
  </div>
</template>
