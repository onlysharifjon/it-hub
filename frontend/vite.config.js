import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
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
