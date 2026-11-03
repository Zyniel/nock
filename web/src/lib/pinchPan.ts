// The touch gestures of the grid's viewport, as a Svelte action: one finger
// pans, two fingers pinch (the zoom follows the ratio of the finger
// distances). The arithmetic is in gridLayout.ts.

import { flushSync } from 'svelte'
import { ZOOM_MIN, clampZoom, distanceBetween, scrollAfterZoom } from './gridLayout'

// What the gestures read and change of the grid: its zoom and the side of its
// cells at that zoom.
export interface PinchPanZoom {
  zoom(): number
  cellSize(): number
  setZoom(zoom: number): void
}

interface Finger {
  clientX: number
  clientY: number
}

// Handle the pinch and pan gestures on a scrolling viewport while it is on the
// page.
export function pinchPan(viewport: HTMLElement, grid: PinchPanZoom): { destroy: () => void } {
  // The fingers now on the screen, with their last known position.
  const fingers = new Map<number, Finger>()
  let startDistance = 0
  let startZoom = ZOOM_MIN

  function onPointerDown(event: PointerEvent): void {
    // Pinching and panning are touch gestures: a mouse or a pen keeps its
    // click on the cell it touched.
    if (event.pointerType !== 'touch') {
      return
    }
    // A first finger starts a new gesture: a finger left over from a pointerup
    // that went missing is forgotten.
    if (event.isPrimary) {
      fingers.clear()
    }
    // The viewport keeps the finger until it lifts, even if the cell it touched
    // is drawn again meanwhile; otherwise its pointerup could go missing and
    // leave a finger that is not there.
    viewport.setPointerCapture(event.pointerId)
    fingers.set(event.pointerId, { clientX: event.clientX, clientY: event.clientY })
    startPinchIfTwoFingers()
  }

  // A pinch measures its ratio against the two fingers on the screen when it
  // started, so each time exactly two fingers are down it starts anew.
  function startPinchIfTwoFingers(): void {
    if (fingers.size !== 2) {
      return
    }
    const [first, second] = [...fingers.values()]
    startDistance = distanceBetween(first, second)
    startZoom = grid.zoom()
  }

  function onPointerMove(event: PointerEvent): void {
    const finger = fingers.get(event.pointerId)
    if (finger === undefined) {
      return
    }
    if (fingers.size === 1) {
      viewport.scrollLeft -= event.clientX - finger.clientX
      viewport.scrollTop -= event.clientY - finger.clientY
    }
    finger.clientX = event.clientX
    finger.clientY = event.clientY
    if (fingers.size === 2 && startDistance > 0) {
      const [first, second] = [...fingers.values()]
      const ratio = distanceBetween(first, second) / startDistance
      const centerX = (first.clientX + second.clientX) / 2
      const centerY = (first.clientY + second.clientY) / 2
      zoomAround(clampZoom(startZoom * ratio), centerX, centerY)
    }
  }

  function onPointerEnd(event: PointerEvent): void {
    fingers.delete(event.pointerId)
    if (fingers.size < 2) {
      startDistance = 0
    }
    startPinchIfTwoFingers()
  }

  // Change the zoom and scroll so the point between the fingers stays put.
  function zoomAround(newZoom: number, centerX: number, centerY: number): void {
    const oldCellSize = grid.cellSize()
    if (newZoom === grid.zoom() || oldCellSize === 0) {
      return
    }
    const box = viewport.getBoundingClientRect()
    const offsetX = centerX - box.left
    const offsetY = centerY - box.top
    const oldScrollLeft = viewport.scrollLeft
    const oldScrollTop = viewport.scrollTop
    grid.setZoom(newZoom)
    // The grid is drawn at the new size before the scroll is set.
    flushSync()
    const newCellSize = grid.cellSize()
    viewport.scrollLeft = scrollAfterZoom(oldScrollLeft, offsetX, oldCellSize, newCellSize)
    viewport.scrollTop = scrollAfterZoom(oldScrollTop, offsetY, oldCellSize, newCellSize)
  }

  viewport.addEventListener('pointerdown', onPointerDown)
  viewport.addEventListener('pointermove', onPointerMove)
  viewport.addEventListener('pointerup', onPointerEnd)
  viewport.addEventListener('pointercancel', onPointerEnd)
  return {
    destroy: () => {
      viewport.removeEventListener('pointerdown', onPointerDown)
      viewport.removeEventListener('pointermove', onPointerMove)
      viewport.removeEventListener('pointerup', onPointerEnd)
      viewport.removeEventListener('pointercancel', onPointerEnd)
    },
  }
}
