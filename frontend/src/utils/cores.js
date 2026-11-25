// Cálculos de cor usados pelo tema: contraste (WCAG), cor de texto automática e variações.
export const hexValido = (v) => typeof v === 'string' && /^#[0-9A-Fa-f]{6}$/.test(v)

const paraRgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16))
const paraHex = (rgb) => '#' + rgb.map((v) => Math.max(0, Math.min(255, Math.round(v))).toString(16).padStart(2, '0')).join('')
const canal = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4 }
const luminancia = (hex) => { const [r, g, b] = paraRgb(hex); return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b) }

export function contraste(a, b) {
  const [x, y] = [luminancia(a), luminancia(b)].sort((m, n) => n - m)
  return (x + 0.05) / (y + 0.05)
}
/** Preto ou branco, o que tiver mais contraste sobre `fundo`. */
export const melhorTexto = (fundo) => (contraste(fundo, '#FFFFFF') >= contraste(fundo, '#000000') ? '#FFFFFF' : '#000000')
/** Mistura `a` com `b`; `t` é a fração de `b` (0 a 1). */
export const misturar = (a, b, t) => { const [A, B] = [paraRgb(a), paraRgb(b)]; return paraHex(A.map((v, i) => v + (B[i] - v) * t)) }
/** Escurece a cor só o necessário para ela ser legível como texto sobre `fundo`. */
export function escurecerAteContraste(cor, fundo = '#FFFFFF', minimo = 4.5) {
  for (let t = 0; t <= 1; t += 0.02) {
    const c = misturar(cor, '#000000', t)
    if (contraste(c, fundo) >= minimo) return c
  }
  return '#000000'
}

export const PADRAO_TEMA = {
  logo: '', cor_menu: '#13201C', cor_destaque: '#1F6F54', login_fundo_tipo: 'cor', login_cor: '#F3F4EF',
  login_imagem: '', login_video: '', caixa_vertical: 'meio', caixa_horizontal: 'centro', caixa_opacidade: 100,
}

export const VARIAVEIS = ['--menu-bg', '--menu-fg', '--menu-fg-mudo', '--menu-linha', '--menu-ativo-bg', '--menu-barra',
  '--acento', '--acento-fg', '--acento-texto']

/** Variáveis CSS derivadas das duas cores do tema (menu e destaque). */
export function variaveisDoTema({ cor_menu, cor_destaque }) {
  const menu = hexValido(cor_menu) ? cor_menu : PADRAO_TEMA.cor_menu
  const acento = hexValido(cor_destaque) ? cor_destaque : PADRAO_TEMA.cor_destaque
  const fg = melhorTexto(menu)
  return {
    '--menu-bg': menu,
    '--menu-fg': fg,
    '--menu-fg-mudo': misturar(fg, menu, 0.3),
    '--menu-linha': misturar(menu, fg, 0.2),
    '--menu-ativo-bg': misturar(menu, fg, 0.14),
    '--menu-barra': contraste(acento, menu) >= 3 ? acento : fg,
    '--acento': acento,
    '--acento-fg': melhorTexto(acento),
    '--acento-texto': escurecerAteContraste(acento),
  }
}
