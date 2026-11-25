import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const alvoApi = env.API_PROXY || 'http://localhost:8000'  // troque em frontend/.env.development se a API estiver em outro lugar
  const proxy = command === 'serve'
    ? Object.fromEntries(['/api', '/media', '/admin'].map((rota) => [rota, { target: alvoApi, changeOrigin: false }]))
    : undefined

  return {
    plugins: [
      vue(),
      VitePWA({
        registerType: 'autoUpdate',
        manifest: {
          name: 'Assistec', short_name: 'Assistec', lang: 'pt-BR',
          description: 'Gestão para assistência técnica',
          theme_color: '#13201C', background_color: '#F3F4EF', display: 'standalone', start_url: '/',
        },
        workbox: { navigateFallbackDenylist: [/^\/api/, /^\/media/, /^\/admin/] },
      }),
    ],
    server: { host: true, proxy },
  }
})
