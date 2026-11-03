// Whether the browser window is wide (spec 046 "Terms"), followed as the
// window changes: the plain pages' frames show their computer form on a wide
// window, and the catalogue its account dialog as a dialog.

import { innerHeight, innerWidth } from 'svelte/reactivity/window'
import { isWideWindow } from './windowForm'

// Tell whether the window is wide now. Read in a template, a `$derived` or an
// `$effect`, the answer is worked out again after each resize or rotation.
export function isWindowWide(): boolean {
  // Both are undefined only outside a browser, where no page runs.
  const width = innerWidth.current ?? 0
  const height = innerHeight.current ?? 0
  return isWideWindow(width, height)
}
