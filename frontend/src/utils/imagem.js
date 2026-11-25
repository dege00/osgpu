function nomeJpeg(nome = 'foto') {
  const base = String(nome).replace(/\.[^.]+$/, '') || 'foto'
  return `${base}.jpg`
}

function erroDeLeitura(file) {
  if (/\.(heic|heif)$/i.test(file.name) || /heic|heif/i.test(file.type)) {
    return new Error('Esta foto está em HEIC/HEIF e não pôde ser convertida neste navegador. Use JPEG ou escolha outra foto.')
  }
  return new Error('Não foi possível ler esta foto. Tente novamente ou escolha outra imagem.')
}

async function carregarImagemReduzida(file, maxLado) {
  if (typeof createImageBitmap !== 'function') throw erroDeLeitura(file)
  const tentativas = [
    { resizeWidth: maxLado, resizeQuality: 'medium', imageOrientation: 'from-image' },
    { resizeWidth: maxLado, resizeQuality: 'medium' },
    { resizeWidth: maxLado },
  ]
  for (const opcoes of tentativas) {
    try {
      return await createImageBitmap(file, opcoes)
    } catch {
      /* tenta opções mais simples */
    }
  }
  throw erroDeLeitura(file)
}

export async function comprimirImagem(file, { maxLado = 1600, qualidade = 0.8 } = {}) {
  if (!file) throw new Error('Nenhuma foto selecionada.')
  if (file.type && !file.type.startsWith('image/') && !/\.(jpe?g|png|webp|heic|heif)$/i.test(file.name)) {
    throw new Error('O arquivo selecionado não é uma imagem.')
  }

  let origem
  let canvas
  let ctx
  try {
    origem = await carregarImagemReduzida(file, maxLado)
    const maiorLado = Math.max(origem.width, origem.height)
    const escala = Math.min(1, maxLado / maiorLado)
    const largura = Math.max(1, Math.round(origem.width * escala))
    const altura = Math.max(1, Math.round(origem.height * escala))
    canvas = document.createElement('canvas')
    canvas.width = largura
    canvas.height = altura
    ctx = canvas.getContext('2d')
    if (!ctx) throw new Error('Não foi possível preparar esta foto.')
    ctx.fillStyle = '#fff'
    ctx.fillRect(0, 0, largura, altura)
    ctx.drawImage(origem, 0, 0, largura, altura)

    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob((resultado) => {
        if (resultado) resolve(resultado)
        else reject(new Error('Não foi possível comprimir esta foto.'))
      }, 'image/jpeg', qualidade)
    })
    return new File([blob], nomeJpeg(file.name), { type: 'image/jpeg', lastModified: Date.now() })
  } finally {
    if (origem && typeof origem.close === 'function') origem.close()
    ctx = null
    if (canvas) {
      canvas.width = 0
      canvas.height = 0
    }
  }
}
