// The touch and pen gestures of the grid's viewport, as a Svelte action: one
// finger or a pen pans, two fingers pinch (the zoom follows the ratio of the
// finger distances). A mouse neither pans nor zooms. The arithmetic is in
// gridLayout.ts.

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

// The pen pressed on the viewport, where it went down and where it is now.
interface Pen {
  pointerId: number
  start: Finger
  clientX: number
  clientY: number
}

// How far a pressed pen moves from where it went down before its press is a
// drag rather than a tap, in CSS px. A drag pans from its first pixel; the
// limit only decides whether the click at the end selects a cell.
const PEN_TAP_LIMIT_PX = 10

// Handle the pinch and pan gestures on a scrolling viewport while it is on the
// page.
export function pinchPan(viewport: HTMLElement, grid: PinchPanZoom): { destroy: () => void } {
  // The fingers now on the screen, with their last known position. A pen is
  // never one of them, so it never pinches.
  const fingers = new Map<number, Finger>()
  let startDistance = 0
  let startZoom = ZOOM_MIN
  // The pen pressed on the viewport, or null while none is.
  let pen: Pen | null = null
  // True once the last pen press moved beyond PEN_TAP_LIMIT_PX: the click the
  // browser sends when it lifts would select the cell now under it, so it is
  // dropped. The next press starts it false again.
  let isPenDragged = false

  function onPointerDown(event: PointerEvent): void {
    isPenDragged = false
    if (event.pointerType === 'pen') {
      onPenDown(event)
    } else if (event.pointerType === 'touch') {
      onFingerDown(event)
    }
  }

  function onPenDown(event: PointerEvent): void {
    pen = {
      pointerId: event.pointerId,
      start: { clientX: event.clientX, clientY: event.clientY },
      clientX: event.clientX,
      clientY: event.clientY,
    }
  }

  function onFingerDown(event: PointerEvent): void {
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
    if (pen !== null && event.pointerId === pen.pointerId) {
      onPenMove(event, pen)
    } else {
      onFingerMove(event)
    }
  }

  function onPenMove(event: PointerEvent, pressedPen: Pen): void {
    // A pen that moves with its tip up was lifted where the viewport did not
    // hear it: it is forgotten and only hovers.
    const isTipDown = (event.buttons & 1) === 1
    if (!isTipDown) {
      pen = null
      return
    }
    viewport.scrollLeft -= event.clientX - pressedPen.clientX
    viewport.scrollTop -= event.clientY - pressedPen.clientY
    pressedPen.clientX = event.clientX
    pressedPen.clientY = event.clientY
    if (isPenDragged) {
      return
    }
    const distance = distanceBetween(pressedPen.start, pressedPen)
    if (distance > PEN_TAP_LIMIT_PX) {
      isPenDragged = true
      // From now on the viewport keeps the pen until it lifts, even if it
      // leaves the viewport. Not before: a captured pen's click goes to the
      // viewport, and a tap's must reach the cell it touched.
      viewport.setPointerCapture(pressedPen.pointerId)
    }
  }

  function onFingerMove(event: PointerEvent): void {
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
    if (event.pointerType === 'pen') {
      return
    }
    fingers.delete(event.pointerId)
    if (fingers.size < 2) {
      startDistance = 0
    }
    startPinchIfTwoFingers()
  }

  // Listens on the whole window, not only on the viewport: a pen pressed on
  // the viewport and lifted beside it, before it moved far enough to be
  // captured, is forgotten too.
  function onPenLifted(event: PointerEvent): void {
    if (pen !== null && event.pointerId === pen.pointerId) {
      pen = null
    }
  }

  // A pressed pen dragged over the clue texts would select them, and the
  // browser would then scroll the viewport towards the selection against the
  // pan: no selection starts while a pen is pressed.
  function onSelectStart(event: Event): void {
    if (pen !== null) {
      event.preventDefault()
    }
  }

  // Runs before the grid's own click handler (it listens on the viewport, in
  // the capture phase) and stops the click that ends a pen drag.
  function onClick(event: MouseEvent): void {
    if (isPenDragged) {
      event.stopPropagation()
      event.preventDefault()
      isPenDragged = false
    }
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
  window.addEventListener('pointerup', onPenLifted)
  window.addEventListener('pointercancel', onPenLifted)
  viewport.addEventListener('selectstart', onSelectStart)
  viewport.addEventListener('click', onClick, true)
  return {
    destroy: () => {
      viewport.removeEventListener('pointerdown', onPointerDown)
      viewport.removeEventListener('pointermove', onPointerMove)
      viewport.removeEventListener('pointerup', onPointerEnd)
      viewport.removeEventListener('pointercancel', onPointerEnd)
      window.removeEventListener('pointerup', onPenLifted)
      window.removeEventListener('pointercancel', onPenLifted)
      viewport.removeEventListener('selectstart', onSelectStart)
      viewport.removeEventListener('click', onClick, true)
    },
  }
}
