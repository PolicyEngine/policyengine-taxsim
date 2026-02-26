import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [tailwindcss(), react()],
  base: '/us/taxsim',
  server: {
    port: 3000,
    open: true,
  },
  build: {
    outDir: 'build',
  },
});
