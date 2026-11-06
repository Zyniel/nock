// The watcher of a list that scrolls (watchListChanges in scrollingLists.ts):
// every caller of one list shares one watcher, and its size observer follows
// the items of the moment, observing only an item that came and letting go of
// an item that went. ResizeObserver and MutationObserver are fakes put on
// globalThis, which record their calls; the list is a plain object with its
// items in `children`.

/// <reference lib="dom" />

import assert from 'node:assert/strict'
import { afterEach, beforeEach, test } from 'node:test'

import { watchListChanges } from '../../web/src/lib/scrollingLists'

// One call of a fake ResizeObserver: what it was asked, on which element.
interface ObserverCall {
  method: 'observe' | 'unobserve'
  target: object
}

class FakeResizeObserver {
  static built: FakeResizeObserver[] = []
  readonly callback: () => void
  readonly calls: ObserverCall[] = []

  constructor(callback: () => void) {
    this.callback = callback
    FakeResizeObserver.built.push(this)
  }

  observe(target: object): void {
    this.calls.push({ method: 'observe', target })
  }

  unobserve(target: object): void {
    this.calls.push({ method: 'unobserve', target })
  }

  disconnect(): void {}
}

class FakeMutationObserver {
  static built: FakeMutationObserver[] = []
  readonly callback: () => void

  constructor(callback: () => void) {
    this.callback = callback
    FakeMutationObserver.built.push(this)
  }

  observe(): void {}

  disconnect(): void {}
}

// A list of the page: its items are its children.
interface FakeList {
  name: string
  children: FakeItem[]
}

interface FakeItem {
  name: string
}

const savedGlobals = new Map<string, unknown>()

beforeEach(() => {
  FakeResizeObserver.built = []
  FakeMutationObserver.built = []
  for (const name of ['ResizeObserver', 'MutationObserver']) {
    savedGlobals.set(name, Reflect.get(globalThis, name))
  }
  Reflect.set(globalThis, 'ResizeObserver', FakeResizeObserver)
  Reflect.set(globalThis, 'MutationObserver', FakeMutationObserver)
})

afterEach(() => {
  for (const [name, value] of savedGlobals) {
    if (value === undefined) {
      Reflect.deleteProperty(globalThis, name)
    } else {
      Reflect.set(globalThis, name, value)
    }
  }
  savedGlobals.clear()
})

function listOf(...itemNames: string[]): FakeList {
  const items: FakeItem[] = []
  for (const name of itemNames) {
    items.push({ name })
  }
  return { name: 'list', children: items }
}

// The module reads only `children` of the list; the rest of an HTMLElement
// is never touched, so the fake stands for one.
function asElement(list: FakeList): HTMLElement {
  return list as unknown as HTMLElement
}

function onlyResizeObserver(): FakeResizeObserver {
  assert.equal(FakeResizeObserver.built.length, 1)
  return FakeResizeObserver.built[0]
}

// The content of the list changed: every content observer hears it.
function changeContent(): void {
  for (const observer of FakeMutationObserver.built) {
    observer.callback()
  }
}

test('two callers of one list share one ResizeObserver and one MutationObserver', () => {
  const list = listOf('first line', 'second line')
  const heard: string[] = []

  watchListChanges(asElement(list), () => heard.push('feed'))
  watchListChanges(asElement(list), () => heard.push('tab stop'))

  const sizeObserver = onlyResizeObserver()
  assert.equal(FakeMutationObserver.built.length, 1)
  sizeObserver.callback()
  assert.deepEqual(heard, ['feed', 'tab stop'])
})

test('the watcher observes the list and each of its items once', () => {
  const list = listOf('first line', 'second line')

  watchListChanges(asElement(list), () => {})

  const sizeObserver = onlyResizeObserver()
  assert.deepEqual(sizeObserver.calls, [
    { method: 'observe', target: list },
    { method: 'observe', target: list.children[0] },
    { method: 'observe', target: list.children[1] },
  ])
})

test('a new line is observed, and only it', () => {
  const list = listOf('first line', 'second line')
  watchListChanges(asElement(list), () => {})
  const sizeObserver = onlyResizeObserver()
  sizeObserver.calls.length = 0

  const newLine = { name: 'new line' }
  list.children.push(newLine)
  changeContent()

  assert.deepEqual(sizeObserver.calls, [{ method: 'observe', target: newLine }])
})

test('a line that left is no longer observed, and nothing else changes', () => {
  const list = listOf('first line', 'second line')
  watchListChanges(asElement(list), () => {})
  const sizeObserver = onlyResizeObserver()
  sizeObserver.calls.length = 0

  const leftLine = list.children[0]
  list.children.shift()
  changeContent()

  assert.deepEqual(sizeObserver.calls, [{ method: 'unobserve', target: leftLine }])
})
