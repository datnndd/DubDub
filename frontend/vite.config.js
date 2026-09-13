import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'path';
import { readFileSync } from 'fs';

const pkg = JSON.parse(readFileSync(path.resolve(__dirname, 'package.json'), 'utf-8'));

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    tailwindcss(),
    react(),
  ],
  define: {
    __APP_VERSION__: JSON.stringify(pkg.version),
  },
  clearScreen: false,
  resolve: {
    preserveSymlinks: false,
    alias: {
      // shadcn/ui convention: `@/…` resolves to `src/…` (mirrored in
      // tsconfig.json `paths` so the type-checker agrees). Lets shadcn
      // primitives import `@/lib/utils` and `npx shadcn add` work unmodified.
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    port: Number(process.env.OMNIVOICE_UI_PORT) || 3901,
    strictPort: true,
    host: false,
  },

  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.test.{js,jsx,ts,tsx}'],
    css: false,
  },
});
