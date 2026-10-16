import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  // In dev, talk to `python manage.py runserver` on :8000.
  server: { proxy: { '/api': 'http://localhost:8000' } },
})
