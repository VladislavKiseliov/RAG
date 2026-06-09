import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: true, // чтобы Vite слушал все интерфейсы внутри докера
    port: 5174, // или 5173, смотря какой у тебя там порт

    // РАЗРЕШАЕМ ХОСТЫ ДЛЯ ОБХОДА БЛОКИРОВКИ:
    allowedHosts: true
  },
})
