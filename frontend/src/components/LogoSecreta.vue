<script setup>
import { computed } from 'vue'
import { painel, tema, urlTema } from '../composables/useTema'

defineProps({ tamanho: { type: Number, default: 30 } })
const src = computed(() => urlTema(tema.logo) || '/icon.svg')

// Três cliques rápidos (até 0,8 s) abrem o painel de personalização. Nada indica que a logo é clicável.
let cliques = []
function clicou() {
  const agora = Date.now()
  cliques = [...cliques.filter((t) => agora - t < 800), agora]
  if (cliques.length >= 3) { cliques = []; painel.aberto = true }
}
</script>
<template>
  <img :src="src" alt="" :width="tamanho" :height="tamanho" class="logo-secreta" draggable="false" @click="clicou" />
</template>
<style>
.logo-secreta { object-fit: contain; border-radius: 6px; user-select: none; -webkit-user-select: none; touch-action: manipulation; -webkit-tap-highlight-color: transparent }
</style>
