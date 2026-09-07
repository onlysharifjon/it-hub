import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Dev rejimida brauzer API'ga to'g'ridan-to'g'ri bormaydi: so'rovlar vite'ning
// o'zi orqali (/api -> DEV_API_TARGET) proxy qilinadi. Sabab — backend CORS
// faqat https://crm.minaracademy.uz ga ruxsat beradi, shuning uchun
// http://localhost:5173 dan qilingan to'g'ridan-to'g'ri so'rovlar brauzerda
// bloklanadi va sahifada hamma ma'lumot bo'sh (null) ko'rinadi. Proxy server
// tomonida ishlagani uchun CORS umuman qo'llanilmaydi.
// Lokal backend bilan ishlash: DEV_API_TARGET=http://127.0.0.1:8001 npm run dev
const DEV_API_TARGET = process.env.DEV_API_TARGET || 'https://crm.minaracademy.uz'
const isLocalTarget = /localhost|127\.0\.0\.1/.test(DEV_API_TARGET)

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: DEV_API_TARGET,
        changeOrigin: true,
        secure: true,
        // Uvicorn to'g'ridan-to'g'ri ishlaganda route'lar ildizda (/auth/login),
        // prod'da esa nginx ularni /api ostida beradi.
        rewrite: isLocalTarget ? (path) => path.replace(/^\/api/, '') : undefined,
        configure: (proxy) => {
          // Origin: http://localhost:5173 ni olib tashlaymiz — aks holda
          // FastAPI CORSMiddleware preflight'ni 400 "Disallowed CORS origin"
          // bilan rad etadi.
          proxy.on('proxyReq', (proxyReq) => proxyReq.removeHeader('origin'))
        },
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // Vendor kodini alohida chunk'larga ajratamiz: ilova kodi o'zgarganda
        // (deyarli har deploy'da) brauzer react/fontawesome'ni qayta yuklamaydi,
        // ular o'z hash'i bilan kesh'da qoladi. Ilgari hammasi bitta ~660KB
        // faylda edi va har bir deploy butun bundle'ni qayta yuklatardi.
        manualChunks: {
          react: ['react', 'react-dom'],
          icons: [
            '@fortawesome/react-fontawesome',
            '@fortawesome/fontawesome-svg-core',
            '@fortawesome/free-solid-svg-icons',
            '@fortawesome/free-regular-svg-icons',
            '@fortawesome/free-brands-svg-icons',
          ],
        },
      },
    },
  },
})
