<script setup>
import { onMounted, ref } from 'vue'
const emit = defineEmits(['salvar'])
const cv = ref(null)
let ctx, desenhando = false, tocou = false
function pos(e) { const r = cv.value.getBoundingClientRect(); return [e.clientX - r.left, e.clientY - r.top] }
onMounted(() => {
  const c = cv.value, r = c.getBoundingClientRect(), d = window.devicePixelRatio || 1
  c.width = r.width * d; c.height = r.height * d
  ctx = c.getContext('2d'); ctx.scale(d, d); ctx.lineWidth = 2.5; ctx.lineCap = 'round'; ctx.strokeStyle = '#13201C'
})
function ini(e) { desenhando = true; tocou = true; cv.value.setPointerCapture(e.pointerId); ctx.beginPath(); ctx.moveTo(...pos(e)) }
function mov(e) { if (!desenhando) return; ctx.lineTo(...pos(e)); ctx.stroke() }
function fim() { desenhando = false }
function limpar() { const c = cv.value; ctx.clearRect(0, 0, c.width, c.height); tocou = false }
function salvar() { if (tocou) emit('salvar', cv.value.toDataURL('image/png')) }
</script>
<template>
  <div>
    <canvas ref="cv" class="assinatura" @pointerdown="ini" @pointermove="mov" @pointerup="fim" @pointercancel="fim"></canvas>
    <div class="acoes" style="margin-top:.5rem">
      <button type="button" class="btn sec" @click="limpar">Limpar</button>
      <button type="button" class="btn" @click="salvar">Salvar assinatura</button>
    </div>
  </div>
</template>
