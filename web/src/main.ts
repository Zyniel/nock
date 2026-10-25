import { mount } from 'svelte'
// The faces of specs/_design/foundation.md « Typography », and no other: Vite builds their
// WOFF2 files into web/dist, so Nock serves them from its own origin (spec 041).
import '@fontsource/source-sans-3/400.css'
import '@fontsource/source-sans-3/500.css'
import '@fontsource/source-sans-3/600.css'
import '@fontsource/source-sans-3/700.css'
import '@fontsource/source-sans-3/500-italic.css'
import '@fontsource/source-sans-3/700-italic.css'
import '@fontsource/ibm-plex-sans-condensed/500.css'
import '@fontsource/ibm-plex-sans-condensed/600.css'
import './app.css'
import App from './App.svelte'

const app = mount(App, {
  target: document.getElementById('app')!,
})

export default app
