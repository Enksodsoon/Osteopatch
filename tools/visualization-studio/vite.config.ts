import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vite';

const studio = fileURLToPath(new URL('.', import.meta.url));
const figures = resolve(studio, '../../docs/visualizations');

export default defineConfig({
  server: { fs: { allow: [studio, figures] } },
});
