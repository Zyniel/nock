import { svelte } from '@sveltejs/vite-plugin-svelte'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [svelte()],
  // No asset inlined as a data: URI: the app's Content-Security-Policy
  // (platform/serving.md rule 12) allows only files of its own origin.
  build: { assetsInlineLimit: 0 },
})
