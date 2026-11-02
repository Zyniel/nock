// The room page's fonts, fetched at once (client/foundation.md rule 5): the grid's
// letters and clues use Source Sans 3 at 500 and IBM Plex Sans Condensed at 600,
// and the browser would only find out which files it needs after it has drawn
// the grid.
//
// Vite turns each `new URL(path, import.meta.url)` into the address of the built
// file, the same one the faces' CSS names (the file keeps its hash). The path
// goes through `node_modules` and not through an `@fontsource/` import: the
// `@fontsource/` imports of `main.ts` are the faces' CSS files, and no others.
const letterFaceUrl = new URL(
  '../../node_modules/@fontsource/source-sans-3/files/source-sans-3-latin-500-normal.woff2',
  import.meta.url,
).href
const clueFaceUrl = new URL(
  '../../node_modules/@fontsource/ibm-plex-sans-condensed/files/ibm-plex-sans-condensed-latin-600-normal.woff2',
  import.meta.url,
).href

// Ask the browser to fetch the `latin` files of the grid's two faces now. A font
// preload needs `crossorigin`, or the browser fetches the file a second time
// for the face.
export function preloadGridFonts(): void {
  for (const href of [letterFaceUrl, clueFaceUrl]) {
    const link = document.createElement('link')
    link.rel = 'preload'
    link.as = 'font'
    link.type = 'font/woff2'
    link.crossOrigin = 'anonymous'
    link.href = href
    document.head.append(link)
  }
}
