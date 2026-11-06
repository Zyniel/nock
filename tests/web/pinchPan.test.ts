// The finger gestures of the grid's viewport (pinchPan.ts): a finger whose
// pointerup went missing is forgotten when the next gesture starts, and the
// viewport captures each finger so that its pointerup is not lost. The
// viewport is a fake EventTarget with the fields the module reads; the
// pointer events are plain Events with the fields of a PointerEvent; the
// window is an EventTarget put on globalThis.

/// <reference lib="dom" />

import assert from 'node:assert/strict'
import { afterEach, beforeEach, test } from 'node:test'

import { pinchPan } from '../../web/src/lib/pinchPan'
import type { PinchPanZoom } from '../../web/src/lib/pinchPan'

const START_SCROLL_LEFT = 500
const START_SCROLL_TOP = 300

class FakeViewport extends EventTarget {
  scrollLeft = START_SCROLL_LEFT
  scrollTop = START_SCROLL_TOP
  readonly capturedPointers: number[] = []

  setPointerCapture(pointerId: number): void {
    this.capturedPointers.push(pointerId)
  }

  getBoundingClientRect(): { left: number; top: number } {
    return { left: 0, top: 0 }
  }
}

// The grid at zoom 1 with cells of 40 px; it records each zoom it is given.
class FakeGrid implements PinchPanZoom {
  currentZoom = 1
  readonly zoomsSet: number[] = []

  zoom(): number {
    return this.currentZoom
  }

  cellSize(): number {
    return 40 * this.currentZoom
  }

  setZoom(zoom: number): void {
    this.zoomsSet.push(zoom)
    this.currentZoom = zoom
  }
}

interface Finger {
  pointerId: number
  isPrimary: boolean
}

const FIRST_FINGER: Finger = { pointerId: 1, isPrimary: true }
const SECOND_FINGER: Finger = { pointerId: 2, isPrimary: false }
const NEW_FINGER: Finger = { pointerId: 3, isPrimary: true }

let hadWindow = false
let savedWindow: unknown = undefined

beforeEach(() => {
  hadWindow = Reflect.has(globalThis, 'window')
  savedWindow = Reflect.get(globalThis, 'window')
  Reflect.set(globalThis, 'window', new EventTarget())
})

afterEach(() => {
  if (hadWindow) {
    Reflect.set(globalThis, 'window', savedWindow)
  } else {
    Reflect.deleteProperty(globalThis, 'window')
  }
})

// pinchPan reads only the fields of FakeViewport and listens on it; the rest
// of an HTMLElement is never touched, so the fake stands for one.
function asElement(viewport: FakeViewport): HTMLElement {
  return viewport as unknown as HTMLElement
}

function send(
  viewport: FakeViewport,
  type: 'pointerdown' | 'pointermove' | 'pointerup',
  finger: Finger,
  clientX: number,
  clientY: number,
): void {
  const event = Object.assign(new Event(type), {
    pointerId: finger.pointerId,
    pointerType: 'touch',
    isPrimary: finger.isPrimary,
    clientX,
    clientY,
    buttons: type === 'pointerup' ? 0 : 1,
  })
  viewport.dispatchEvent(event)
}

test('a new first finger after a lost pointerup pans with no zoom', () => {
  const viewport = new FakeViewport()
  const grid = new FakeGrid()
  pinchPan(asElement(viewport), grid)

  // Two fingers pinch; the first one's pointerup never comes.
  send(viewport, 'pointerdown', FIRST_FINGER, 100, 100)
  send(viewport, 'pointerdown', SECOND_FINGER, 200, 100)
  send(viewport, 'pointerup', SECOND_FINGER, 200, 100)
  // A new gesture: one finger down 50 px from where the first one was left,
  // then 50 px farther from it.
  send(viewport, 'pointerdown', NEW_FINGER, 150, 100)
  send(viewport, 'pointermove', NEW_FINGER, 200, 100)

  assert.deepEqual(grid.zoomsSet, [])
  assert.equal(viewport.scrollLeft, START_SCROLL_LEFT - 50)
  assert.equal(viewport.scrollTop, START_SCROLL_TOP)
})

test('the viewport captures each finger that goes down on it', () => {
  const viewport = new FakeViewport()
  pinchPan(asElement(viewport), new FakeGrid())

  send(viewport, 'pointerdown', FIRST_FINGER, 100, 100)
  send(viewport, 'pointerdown', SECOND_FINGER, 200, 100)

  assert.deepEqual(viewport.capturedPointers, [FIRST_FINGER.pointerId, SECOND_FINGER.pointerId])
})
