import { mount } from 'svelte'
// The faces of specs/_design/foundation.md « Typography », and no other, in their `latin`
// and `latin-ext` subsets only: Vite builds their WOFF2 files into web/dist, so Nock serves
// them from its own origin (spec 041).
import '@fontsource/source-sans-3/latin-400.css'
import '@fontsource/source-sans-3/latin-ext-400.css'
import '@fontsource/source-sans-3/latin-500.css'
import '@fontsource/source-sans-3/latin-ext-500.css'
import '@fontsource/source-sans-3/latin-600.css'
import '@fontsource/source-sans-3/latin-ext-600.css'
import '@fontsource/source-sans-3/latin-700.css'
import '@fontsource/source-sans-3/latin-ext-700.css'
import '@fontsource/source-sans-3/latin-500-italic.css'
import '@fontsource/source-sans-3/latin-ext-500-italic.css'
import '@fontsource/source-sans-3/latin-700-italic.css'
import '@fontsource/source-sans-3/latin-ext-700-italic.css'
import '@fontsource/ibm-plex-sans-condensed/latin-500.css'
import '@fontsource/ibm-plex-sans-condensed/latin-ext-500.css'
import '@fontsource/ibm-plex-sans-condensed/latin-600.css'
import '@fontsource/ibm-plex-sans-condensed/latin-ext-600.css'
import './app.css'
import App from './App.svelte'

const app = mount(App, {
  target: document.getElementById('app')!,
})

export default app
