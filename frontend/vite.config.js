import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite' // 1. Add this import

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(), // 2. Add this to the array
  ],
})