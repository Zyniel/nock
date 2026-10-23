// Wide and narrow windows (spec 043 "Which layout", spec 046 "Terms").
//
// The room shows its column layout and its computer top bar on a wide window,
// and the plain pages (the catalogue, the entry pages, the page not found)
// their computer form. Every other window is narrow.

export const COLUMN_MIN_WIDTH_PX = 900
export const LOW_WINDOW_PX = 500

// Tell whether a window of `width` by `height` CSS px is wide: landscape (wider
// than high), at least COLUMN_MIN_WIDTH_PX wide and more than LOW_WINDOW_PX
// high. A portrait tablet (768 by 1024) and a phone on its side (740 by 360)
// are narrow.
export function isWideWindow(width: number, height: number): boolean {
  const isLandscape = width > height
  return isLandscape && width >= COLUMN_MIN_WIDTH_PX && height > LOW_WINDOW_PX
}
